from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import sqlite3
import locale

app = Flask(__name__)
app.secret_key = 'secret_key'

# Configuração do locale para formatação de números
locale.setlocale(locale.LC_ALL, '')

# Filtro personalizado para formatar números
@app.template_filter('number_format')
def number_format(value, decimal_places=2):
    try:
        # Usa locale.currency para formatar como moeda, ajustando a precisão
        return locale.format_string(f"%.{decimal_places}f", value, grouping=True)
    except (ValueError, TypeError):
        return value

# Configurar locale para formatação de moeda
locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')

@app.template_filter('format_currency')
def format_currency(value):
    return locale.currency(value, grouping=True)

# Configuração do banco de dados
def configurar_bd():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS lanches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            preco REAL NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Bebidas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            preco REAL NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pedidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            itens TEXT NOT NULL,
            total REAL NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    
    cursor.execute('SELECT COUNT(*) FROM lanches')
    if cursor.fetchone()[0] == 0:
        lanches_iniciais = [
            ("X-salada", 7.00),
            ("X-Tudo", 15.00),
            ("Pizza", 40.00),
            ("Kikão", 4.00),
            ("Batata Frita", 8.00)
        ]
        cursor.executemany('INSERT INTO lanches (nome, preco) VALUES (?, ?)', lanches_iniciais)

    cursor.execute('SELECT COUNT(*) FROM Bebidas')
    if cursor.fetchone()[0] == 0:
        bebidas_iniciais = [
            ("Bare 2L", 6.00),
            ("Magistral 2L", 4.00),
            ("Coca-cola 2L", 8.00),
            ("Tuchaua 2L", 5.00),
            ("Real 2L", 4.50)
        ]
        cursor.executemany('INSERT INTO Bebidas (nome, preco) VALUES (?, ?)', bebidas_iniciais)
    
    conn.commit()
    conn.close()
configurar_bd()

# Função para atualizar o banco de dados com a coluna 'categoria'
def atualizar_bd():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    # Adicionar a coluna 'categoria'
    try:
        cursor.execute('ALTER TABLE lanches ADD COLUMN categoria TEXT DEFAULT "Lanche"')
    except sqlite3.OperationalError:
        pass  # Ignora o erro caso a coluna já exista

        # Adicionar a coluna 'categoria'
    try:
        cursor.execute('ALTER TABLE Bebidas ADD COLUMN categoria TEXT DEFAULT "Bebida"')
    except sqlite3.OperationalError:
        pass  # Ignora o erro caso a coluna já exista
    
    # Atualizar as categorias dos lanches
    cursor.execute("UPDATE lanches SET categoria = 'Lanche' WHERE nome IN ('X-salada', 'X-Tudo', 'Pizza', 'Kikão', 'Batata Frita')")
    # Atualizar as categorias das Bebidas
    cursor.execute("UPDATE Bebidas SET categoria = 'Bebida' WHERE nome IN ('Bare', 'Magistral', 'Coca-cola', 'Tuchaua', 'Real')")
    
    conn.commit()
    conn.close()

# Execute a função para atualizar o banco de dados

atualizar_bd()

# Decorador para proteger rotas
def login_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor, faça login para acessar esta página.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrap

# Rota para página de registro
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, hashed_password))
        conn.commit()
        conn.close()
        
        flash('Registro realizado com sucesso! Por favor, faça login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

# Rota para página de login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        conn.close()
        
        if user and check_password_hash(user[2], password):
            session['user_id'] = user[0]
            session['username'] = user[1]
            return redirect(url_for('index'))
        else:
            flash('Login falhou. Verifique suas credenciais e tente novamente.', 'danger')
    
    return render_template('login.html')

# Rota para logout
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    flash('Você foi desconectado.', 'success')
    return redirect(url_for('index'))

# Rota para a página inicial que exibe os lanches
@app.route('/')
def index():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    # Selecionando os lanches por categoria
    cursor.execute("SELECT * FROM lanches WHERE categoria = 'Lanche'")
    lanches = cursor.fetchall()
    
    cursor.execute("SELECT * FROM Bebidas WHERE categoria = 'Bebida'")
    bebidas = cursor.fetchall()
    
    conn.close()
    
    # Passando as categorias para o template
    return render_template('index.html', lanches=lanches, bebidas=bebidas)

# Rota para adicionar itens ao carrinho
@app.route('/add_to_cart/<int:item_id>/<string:item_type>')
@login_required
def add_to_cart(item_id, item_type):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    if item_type == 'lanche':
        cursor.execute('SELECT * FROM lanches WHERE id = ?', (item_id,))
        item = cursor.fetchone()
    elif item_type == 'bebida':
        cursor.execute('SELECT * FROM Bebidas WHERE id = ?', (item_id,))
        item = cursor.fetchone()
    else:
        flash('Tipo de item inválido.', 'danger')
        return redirect(url_for('index'))

    conn.close()

    if 'cart' not in session:
        session['cart'] = []

    session['cart'].append({
        'id': item[0],
        'nome': item[1],
        'preco': item[2],
        'tipo': item_type
    })
    session.modified = True
    
    return redirect(url_for('index'))

# Remover itens do carrinho
@app.route('/remove_from_cart/<int:id>')
@login_required
def remove_from_cart(id):
    cart = session.get('cart', [])
    cart = [item for item in cart if item['id'] != id]
    session['cart'] = cart
    session.modified = True
    flash('Item removido do carrinho!', 'success')
    return redirect(url_for('view_cart'))


# Rota para exibir o carrinho
@app.route('/cart')
@login_required
def view_cart():
    cart = session.get('cart', [])
    total = sum(item['preco'] for item in cart)
    return render_template('cart.html', cart=cart, total=total)

# Rota para finalizar o pedido
@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    if request.method == 'POST':
        metodo_pagamento = request.form.get('metodo_pagamento')
        cart = session.get('cart', [])
        if not cart:
            return redirect(url_for('index'))

        total = sum(item['preco'] for item in cart)
        itens = ', '.join([f"{item['nome']} ({item['tipo']})" for item in cart])

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('INSERT INTO pedidos (user_id, itens, total) VALUES (?, ?, ?)', (session['user_id'], itens, total))
        conn.commit()
        conn.close()

        session.pop('cart', None)

        # Redirecionar ou exibir a página de confirmação com base no método de pagamento
        if metodo_pagamento == 'cartao':
            return render_template('pedido_finalizado.html', total=total, metodo_pagamento=metodo_pagamento)
        if metodo_pagamento == 'pix':
            return render_template('pedido_finalizado.html', total=total, metodo_pagamento=metodo_pagamento)
        elif metodo_pagamento == 'dinheiro':
            return render_template('pedido_finalizado.html', total=total, metodo_pagamento=metodo_pagamento)

    return render_template('checkout.html', total=total)

#rota para pag de finalização de pedido
@app.route('/pedido_finalizado')
def pedido_finalizado():
    return render_template('pedido_finalizado.html')

# Rota para exibir o histórico de pedidos
@app.route('/orders')
@login_required
def orders():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM pedidos WHERE user_id = ?', (session['user_id'],))
    pedidos = cursor.fetchall()
    conn.close()
    return render_template('orders.html', pedidos=pedidos)

# Administração de lanches (CRUD)
@app.route('/admin')
@login_required
def admin():
    if session['username'] != 'admin':
        flash('Acesso negado!', 'danger')
        return redirect(url_for('index'))

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    # Buscar lanches
    cursor.execute('SELECT * FROM lanches')
    lanches = cursor.fetchall()
    
    # Buscar bebidas
    cursor.execute('SELECT * FROM Bebidas')
    bebidas = cursor.fetchall()
    
    conn.close()
    
    return render_template('admin.html', lanches=lanches, bebidas=bebidas)

@app.route('/admin/add', methods=['POST'])
@login_required
def admin_add():
    if session['username'] != 'admin':
        flash('Acesso negado!', 'danger')
        return redirect(url_for('index'))

    nome = request.form['nome']
    preco = request.form['preco']
    
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO lanches (nome, preco) VALUES (?, ?)', (nome, preco))
    conn.commit()
    conn.close()
    
    flash('Lanche adicionado com sucesso!', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/add_bebida', methods=['POST'])
@login_required
def admin_add_bebida():
    if session['username'] != 'admin':
        flash('Acesso negado!', 'danger')
        return redirect(url_for('index'))

    nome = request.form['nome']
    preco = request.form['preco']
    
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO Bebidas (nome, preco) VALUES (?, ?)', (nome, preco))
    conn.commit()
    conn.close()
    
    flash('Bebida adicionada com sucesso!', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/delete/<int:id>')
@login_required
def admin_delete(id):
    if session['username'] != 'admin':
        flash('Acesso negado!', 'danger')
        return redirect(url_for('index'))

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM lanches WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    
    flash('Lanche removido com sucesso!', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def admin_edit(id):
    if session['username'] != 'admin':
        flash('Acesso negado!', 'danger')
        return redirect(url_for('index'))

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    if request.method == 'POST':
        nome = request.form['nome']
        preco = request.form['preco']
        cursor.execute('UPDATE lanches SET nome = ?, preco = ? WHERE id = ?', (nome, preco, id))
        conn.commit()
        conn.close()
        flash('Lanche atualizado com sucesso!', 'success')
        return redirect(url_for('admin'))
    else:
        cursor.execute('SELECT * FROM lanches WHERE id = ?', (id,))
        lanche = cursor.fetchone()
        conn.close()
        return render_template('edit_lanche.html', lanche=lanche)

@app.route('/admin/edit_bebida/<int:id>', methods=['GET', 'POST'])
@login_required
def admin_edit_bebida(id):
    if session['username'] != 'admin':
        flash('Acesso negado!', 'danger')
        return redirect(url_for('index'))

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    if request.method == 'POST':
        nome = request.form['nome']
        preco = request.form['preco']
        cursor.execute('UPDATE Bebidas SET nome = ?, preco = ? WHERE id = ?', (nome, preco, id))
        conn.commit()
        conn.close()
        flash('Bebida atualizada com sucesso!', 'success')
        return redirect(url_for('admin'))
    else:
        cursor.execute('SELECT * FROM Bebidas WHERE id = ?', (id,))
        bebida = cursor.fetchone()
        conn.close()
        return render_template('edit_bebida.html', bebida=bebida)

@app.route('/admin/delete_bebida/<int:id>')
@login_required
def admin_delete_bebida(id):
    if session['username'] != 'admin':
        flash('Acesso negado!', 'danger')
        return redirect(url_for('index'))

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM Bebidas WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    
    flash('Bebida removida com sucesso!', 'success')
    return redirect(url_for('admin'))

if __name__ == '__main__':
    app.run()
