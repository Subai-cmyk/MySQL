from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from werkzeug.security import generate_password_hash, check_password_hash
import time
from openai import OpenAI

app = Flask(__name__)

# --- 配置 ---
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:123456@localhost/smart_lib_db' # 改密码！
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'your_secret_key_here' # 用于 session 加密，随便填

db = SQLAlchemy(app)

# --- 模型定义 ---
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='student')

class Book(db.Model):
    __tablename__ = 'books'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    author = db.Column(db.String(100), nullable=False)
    genre = db.Column(db.String(50))
    price = db.Column(db.Numeric(10, 2))
    rating = db.Column(db.Float)
    summary = db.Column(db.Text)
    status = db.Column(db.String(20), default='可借阅')

    # 新增字段
    borrower_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    borrow_date = db.Column(db.DateTime)

    # 建立关系，方便查询借书人的名字
    borrower = db.relationship('User', backref='borrowed_books')

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'author': self.author,
            'genre': self.genre,
            'price': float(self.price) if self.price else 0,
            'rating': self.rating,
            'status': self.status,
            'summary': self.summary,
            'borrower_name': self.borrower.username if self.borrower else None,
            'borrow_date': self.borrow_date.strftime('%Y-%m-%d %H:%M') if self.borrow_date else None
        }

# --- 路由：页面 ---

@app.route('/')
def login_page():
    # 首页改为登录页
    return render_template('login.html')

@app.route('/admin')
def admin_page():
    if session.get('role') != 'admin':
        return redirect('/')
    return render_template('admin.html', username=session.get('username'))

@app.route('/student')
def student_page():
    if session.get('role') != 'student':
        return redirect('/')
    return render_template('student.html', username=session.get('username'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# --- API：认证 (Auth) ---

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    role = data.get('role', 'student') # 默认注册为学生

    if User.query.filter_by(username=username).first():
        return jsonify({'success': False, 'message': '用户名已存在'})

    # 密码加密存储
    hashed_pw = generate_password_hash(password)
    new_user = User(username=username, password=hashed_pw, role=role)
    db.session.add(new_user)
    db.session.commit()
    return jsonify({'success': True, 'message': '注册成功，请登录'})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    user = User.query.filter_by(username=username).first()

    # 验证密码
    if user and check_password_hash(user.password, password):
        session['user_id'] = user.id
        session['username'] = user.username
        session['role'] = user.role
        return jsonify({'success': True, 'role': user.role})

    return jsonify({'success': False, 'message': '用户名或密码错误'})

# --- API：图书管理 ---

@app.route('/api/books', methods=['GET'])
def get_books():
    books = Book.query.order_by(Book.id.asc()).all()
    return jsonify([b.to_dict() for b in books])

@app.route('/api/books', methods=['POST'])
def add_book():
    data = request.json
    new_book = Book(
        title=data['title'],
        author=data['author'],
        genre=data['genre'],
        price=data['price'],
        rating=data['rating'],
        summary=data.get('summary', ''),
        status='可借阅'
    )
    db.session.add(new_book)
    db.session.commit()
    return jsonify({'message': '添加成功'})

@app.route('/api/books/<int:id>', methods=['DELETE'])
def delete_book(id):
    book = Book.query.get_or_404(id)
    db.session.delete(book)
    db.session.commit()
    return jsonify({'message': '删除成功'})

# --- API：借还书 (核心修改) ---

@app.route('/api/borrow/<int:id>', methods=['POST'])
def borrow_book(id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'message': '请先登录'}), 401

    book = Book.query.get_or_404(id)
    if book.status == '可借阅':
        book.status = '已借出'
        book.borrower_id = user_id
        book.borrow_date = func.now() # 记录当前时间
        db.session.commit()
        return jsonify({'success': True, 'message': '借阅成功！'})
    return jsonify({'success': False, 'message': '手慢了，书已被借走'})

@app.route('/api/return/<int:id>', methods=['POST'])
def return_book(id):
    # 学生只能还自己借的书，管理员可以还任何书
    user_id = session.get('user_id')
    role = session.get('role')

    book = Book.query.get_or_404(id)

    if role == 'student' and book.borrower_id != user_id:
        return jsonify({'success': False, 'message': '这不是你借的书，无法归还'}), 403

    book.status = '可借阅'
    book.borrower_id = None
    book.borrow_date = None
    db.session.commit()
    return jsonify({'success': True, 'message': '还书成功！'})

# --- API：管理员高级统计 (新增) ---

@app.route('/api/admin/dashboard', methods=['GET'])
def admin_dashboard_stats():
    # 1. 统计每本书的总数和被借出的数量 (按书名分组)
    # SQL逻辑: SELECT title, COUNT(*) total, SUM(CASE WHEN status='已借出' THEN 1 ELSE 0 END) borrowed FROM books GROUP BY title

    books_stats = db.session.query(
        Book.title,
        func.count(Book.id).label('total_count'),
        func.sum(func.if_(Book.status == '已借出', 1, 0)).label('borrowed_count')
    ).group_by(Book.title).all()

    overview_data = []
    for stat in books_stats:
        overview_data.append({
            'title': stat.title,
            'total': stat.total_count,
            'borrowed': int(stat.borrowed_count) if stat.borrowed_count else 0
        })

    # 2. 获取当前借阅详情列表 (谁借了哪本)
    borrowed_books = Book.query.filter_by(status='已借出').all()
    borrow_log = []
    for book in borrowed_books:
        borrow_log.append({
            'book_id': book.id,
            'title': book.title,
            'borrower': book.borrower.username if book.borrower else '未知',
            'date': book.borrow_date.strftime('%Y-%m-%d %H:%M') if book.borrow_date else ''
        })

    return jsonify({
        'overview': overview_data,
        'logs': borrow_log
    })

# --- 智能 AI 助手接口 (放在 app.py 末尾，run 之前) ---
@app.route('/api/ai-agent', methods=['POST'])
def ai_agent():
    data = request.json
    user_input = data.get('prompt', '').strip()
    user_role = session.get('role', 'visitor')

    # 1. --- RAG检索：先查数据库 ---
    # 模糊搜索书名
    found_book = Book.query.filter(Book.title.like(f'%{user_input}%')).first()

    db_context = ""
    if found_book:
        # 整理书籍信息
        borrow_info = ""
        if found_book.status == '已借出':
            if user_role == 'admin':
                borrower_name = found_book.borrower.username if found_book.borrower else "未知"
                borrow_info = f"被用户【{borrower_name}】借走，归还时间未知。"
            else:
                borrow_info = "已被借出，暂时无货。"
        else:
            borrow_info = "在架上，状态【可借阅】。"

        db_context = (
            f"【系统数据库检索结果】\n"
            f"书名：《{found_book.title}》\n"
            f"作者：{found_book.author}\n"
            f"评分：{found_book.rating}\n"
            f"当前状态：{borrow_info}\n"
            f"简介：{found_book.summary}"
        )
    else:
        db_context = "【系统数据库检索结果】\n数据库中未找到名为“" + user_input + "”的书籍。"

    # 2. --- 调用通义千问 API (OpenAI 兼容模式) ---
    client = OpenAI(
        api_key="sk-f3b26d179d354d6a9efeab645d1b86bd",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
    )

    try:
        response = client.chat.completions.create(
            # 使用通义千问模型：qwen-plus (推荐), qwen-max (更强), qwen-turbo (更快)
            model="qwen-plus",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是一个智慧、博学的图书馆管理员。请根据提供的【数据库检索结果】回答用户问题。\n"
                        "要求：\n"
                        "1. 优先依据数据库结果回答库存和状态。\n"
                        "2. 如果数据库没书，可以发挥你的博学知识，推荐同类书籍，但要明确说明“本馆暂时没有”。\n"
                        "3. 语气亲切自然，适当使用Emoji。"
                    )
                },
                {
                    "role": "user",
                    "content": f"用户问题：{user_input}\n\n{db_context}"
                }
            ],
            stream=False
        )
        reply = response.choices[0].message.content

    except Exception as e:
        print(f"通义千问 API 报错: {e}")
        reply = "系统连接阿里云超时，请检查网络或 API Key 是否正确。"

    return jsonify({'reply': reply})

if __name__ == '__main__':
    app.run(debug=True, port=5000)