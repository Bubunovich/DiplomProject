from flask import Flask, render_template, request, redirect, url_for, session
import pyodbc

app = Flask(__name__)
app.secret_key = 'your_secret_key'

def get_db_connection(): #подключение к базе данных
    server = '192.168.0.22,1433'  # имя сервера и порт
    database = 'GATTT'
    username = 'SA'
    password = 'MyStrongPass123'
    driver = '{ODBC Driver 17 for SQL Server}'  # ODBC драйвер для подключения к sql server
    connection_string = f'DRIVER={driver};SERVER={server};DATABASE={database};UID={username};PWD={password}'
    conn = pyodbc.connect(connection_string)
    return conn

@app.route('/')
def main(): #главная страница
    return render_template('main.html')


@app.route('/products', methods=['GET', 'POST'])
def products(): #страница каталога товаров
    conn = get_db_connection()
    cursor = conn.cursor()

    search_query = request.args.get('search', '')

    if search_query:
        cursor.execute('''
            SELECT * FROM Product 
            WHERE LOWER(Product_Name) LIKE LOWER(?)
            OR LOWER(Product_Color) LIKE LOWER(?)
            ''', (f'%{search_query}%', f'%{search_query}%'))
    else:
        cursor.execute('SELECT * FROM Product')

    product = cursor.fetchall()
    conn.close()
    return render_template('products.html', products=product, search_query=search_query)

@app.route('/products/<int:product_id>')
def product_view(product_id): #страница просмотра товара
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM Product WHERE id = ?', (product_id,))
    product = cursor.fetchone()

    if product:
        return render_template('product_view.html', products=product)
    else:
        return "Товар не найден", 404

@app.route('/registration', methods=['GET', 'POST'])
def registration(): #страница регистрации пользователя
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        user_name = request.form['User_Name']
        user_surname = request.form['User_Surname']
        user_patronymic = request.form['User_Patronymic']
        user_login = request.form['User_Login']
        user_password = request.form['User_Password']
        user_email = request.form['User_Email']

        cursor.execute("SELECT * FROM Users WHERE User_Login = ?", (user_login,))
        if cursor.fetchone():
            return "Пользователь с таким логином уже существует"

        cursor.execute("""
            INSERT INTO Users (User_Surname, User_Name, User_Patronymic, User_Login, User_Password, User_Email)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (user_surname, user_name, user_patronymic, user_login, user_password, user_email)
        )
        conn.commit()
        return redirect(url_for('login'))

    return render_template('registration.html')

@app.route('/login', methods=['GET', 'POST'])
def login(): #страница авторизации пользователя
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        user_login = request.form['User_Login']
        user_password = request.form['User_Password']

        cursor.execute("SELECT * FROM Users WHERE User_Login = ? AND User_Password = ?", (user_login, user_password))
        user = cursor.fetchone()

        if user:
            session['User_Id'] = user.Id
            session['User_Login'] = user.User_Login
            session['User_Password'] = user.User_Password
            session['User_Surname'] = user.User_Surname
            session['User_Name'] = user.User_Name
            session['User_Patronymic'] = user.User_Patronymic
            return redirect(url_for('products'))  # или на главную
        else:
            return "Неверный логин или пароль"

    return render_template('login.html')

@app.route('/profile')
def profile(): #страница профиля пользователя
    conn = get_db_connection()
    cursor = conn.cursor()

    if 'User_Id' in session:
        user_id = session.get('User_Id')

        cursor.execute("""
                SELECT Orders.Id, Orders.Order_Date, OrderItem.OrderItem_Price,
                    Product.Product_Name, Product.Product_Image, OrderItem.OrderItem_Quantity
                FROM Orders
                JOIN OrderItem ON Orders.Id = OrderItem.OrderItem_Id
                JOIN Product ON OrderItem.OrderItem_Product = Product.Id
                WHERE Orders.Order_User = ?
                ORDER BY Orders.Order_Date DESC
            """, user_id)

        orders = cursor.fetchall()

        group_orders = {}
        for order in orders:
            order_id = order.Id
            if order_id not in group_orders:
                group_orders[order_id] = {
                    'id': order.Id,
                    'date': order.Order_Date,
                    'item': [],
                    'total_price': 0
                }
            group_orders[order_id]['item'].append({
                'name': order.Product_Name,
                'image': order.Product_Image,
                'quantity': order.OrderItem_Quantity,
                'price': order.OrderItem_Price
            })

            group_orders[order_id]['total_price'] = sum(
                item['price'] * item['quantity']
                for item in group_orders[order_id]['item']
            )

        return render_template('profile.html',
                               user_login=session.get('User_Login'),
                               user_surname=session.get('User_Surname'),
                               user_name=session.get('User_Name'),
                               user_patronymic=session.get('User_Patronymic'),
                               orders=list(group_orders.values()))
    else:
        return redirect(url_for('login'))


@app.route('/logout', methods=['POST'])
def logout(): #выход пользователя из аккаунта
    session.clear()
    return redirect(url_for('login'))

@app.route('/add_busket/<int:product_id>')
def add_busket(product_id): #добавление товаров в корзину
    if 'User_Id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()
    user_id = session.get('User_Id')

    cursor.execute("SELECT * FROM Busket WHERE Busket_User = ? AND Busket_Product = ?", (user_id, product_id))
    item = cursor.fetchone()

    if item:
        cursor.execute("UPDATE Busket SET Busket_Quantity = Busket_Quantity + 1 WHERE Busket_User = ? AND Busket_Product = ?",
                       (user_id, product_id))
    else:
        cursor.execute("INSERT INTO Busket (Busket_User, Busket_Product, Busket_Quantity) VALUES (?, ?, ?)",
                       (user_id, product_id, 1))

    conn.commit()
    conn.close()

    return redirect(url_for('products'))

@app.route('/busket')
def busket(): #страница корзины
    if 'User_Id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    user_id = session.get('User_Id')

    cursor.execute("""
        SELECT Product.Id, Product.Product_Name, Product.Product_Color, Product.Product_Price, Product.Product_Image, Busket.Busket_Quantity
        FROM Busket
        JOIN Product ON Busket.Busket_Product = Product.Id
        WHERE Busket.Busket_User = ?
    """, (user_id,))

    product = cursor.fetchall()
    conn.close()

    total_price = sum(products.Product_Price * products.Busket_Quantity for products in product)

    return render_template('busket.html', products=product, total_price=total_price)

@app.route('/remove_busket/<int:product_id>')
def remove_busket(product_id): #удаление товаров из корзины
    if 'User_Id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()
    user_id = session.get('User_Id')

    cursor.execute("DELETE FROM Busket WHERE Busket_User = ? AND Busket_Product = ?", (user_id, product_id))
    conn.commit()
    conn.close()

    return redirect(url_for('busket'))

@app.route('/check_address', methods=['POST'])
def check_address(): # Проверка на наличие адреса
    if 'User_Id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    user_id = session['User_Id']

    cursor.execute("SELECT * FROM Address WHERE Address_User = ?", (user_id,))
    address = cursor.fetchone()

    conn.close()

    if address:
        return redirect(url_for('order'))
    else:
        return redirect(url_for('address'))

@app.route('/order')
def order(): #добавление товаров в заказ
    conn = get_db_connection()
    cursor = conn.cursor()
    user_id = session.get('User_Id')

    cursor.execute("SELECT * FROM Busket WHERE Busket_User = ?", (user_id,))
    product = cursor.fetchall()

    if not product:
        return "Корзина пуста"

    cursor.execute("INSERT INTO Orders (Order_User) VALUES (?)", (user_id,))
    order_id = cursor.execute("SELECT @@IDENTITY").fetchone()[0]

    for products in product:
        cursor.execute("SELECT Product_Price FROM Product WHERE Id = ?", (products.Busket_Product,))
        product_price = cursor.fetchone()[0]

        cursor.execute("""
            INSERT INTO OrderItem (OrderItem_Id, OrderItem_Product, OrderItem_Quantity, OrderItem_Price)
            VALUES (?, ?, ?, ?)
        """, (order_id, products.Busket_Product, products.Busket_Quantity, product_price))

    cursor.execute("DELETE FROM Busket WHERE Busket_User = ?", (user_id,))
    conn.commit()
    conn.close()

    return "Спасибо! Заказ оформлен."

@app.route('/address', methods=['GET', 'POST'])
def address(): #добавление адреса пользователя
    if request.method == 'POST':
        address_country = request.form.get('Address_Country')
        address_city = request.form.get('Address_City')
        address_street = request.form.get('Address_Street')
        address_house = request.form.get('Address_Home')
        address_user = session.get('User_Id')

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO Address (Address_Country, Address_City, Address_Street, Address_Home, Address_User)
            VALUES (?, ?, ?, ?, ?)
        """, (address_country, address_city, address_street, address_house, address_user))

        conn.commit()
        conn.close()

        return redirect(url_for('order'))

    return render_template('address.html')

@app.route('/about')
def about(): #страница о нас
    return render_template('about.html')


if __name__ == '__main__':
    app.run(debug=True)