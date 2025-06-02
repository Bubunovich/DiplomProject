from flask import Flask, render_template, request, redirect, url_for, session, flash
import pyodbc
from flask_mail import Mail, Message

app = Flask(__name__)
app.secret_key = 'my_secret_key'

def get_db_connection(): #подключение к базе данных
    server = '172.20.10.2,1433'  # имя сервера и порт
    database = 'GATTT'
    username = 'SA'
    password = 'MyStrongPass123'
    driver = '{ODBC Driver 17 for SQL Server}'  # ODBC драйвер для подключения к sql server
    connection_string = f'DRIVER={driver};SERVER={server};DATABASE={database};UID={username};PWD={password}'
    conn = pyodbc.connect(connection_string)
    return conn

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'nikitalucenko2005@gmail.com'
app.config['MAIL_PASSWORD'] = 'hccm ihux gdgj flyl'
app.config['MAIL_DEFAULT_SENDER'] = 'nikitalucenko2005@gmail.com'

mail = Mail(app)


@app.route('/')
def main(): #главная страница
    return render_template('main.html')


@app.route('/products', methods=['GET'])
def products(): #страница каталога товаров
    conn = get_db_connection()
    cursor = conn.cursor()

    search_query = request.args.get('search', '')

    if search_query:
        cursor.execute('''
            SELECT * FROM Product 
            WHERE LOWER(Product_Name) LIKE LOWER(?)
            OR LOWER(Product_Color) LIKE LOWER(?)
            OR LOWER(Product_Description) LIKE LOWER(?)
            ''', (f'%{search_query}%', f'%{search_query}%', f'%{search_query}%'))
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
        flash('Успешная регистрация!','popup')
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
            flash('Успешная авторизация!','popup')
            return redirect(url_for('products'))
        else:
            flash('Неверный логин или пароль!','popup')
            return redirect(url_for('login'))

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
def order():
    conn = get_db_connection()
    cursor = conn.cursor()
    user_id = session.get('User_Id')

    cursor.execute("SELECT * FROM Busket WHERE Busket_User = ?", (user_id,))
    basket_items = cursor.fetchall()

    # Создаем заказ
    cursor.execute("""
        INSERT INTO Orders (Order_User) 
        OUTPUT inserted.Id
        VALUES (?)
    """, (user_id,))
    order_id = cursor.fetchone()[0]

    # Подготавливаем данные для письма
    order_details = []
    total_amount = 0

    for item in basket_items:
        # Получаем информацию о товаре
        cursor.execute("""
            SELECT Product_Name, Product_Price 
            FROM Product 
            WHERE Id = ?
        """, (item.Busket_Product,))
        product = cursor.fetchone()
        
        product_name = product[0]
        price = product[1]
        quantity = item.Busket_Quantity
        item_total = price * quantity
        total_amount += item_total

        order_details.append({
            'name': product_name,
            'price': price,
            'quantity': quantity,
            'total': item_total
        })

        cursor.execute("""
            INSERT INTO OrderItem (OrderItem_Id, OrderItem_Product, OrderItem_Quantity, OrderItem_Price)
            VALUES (?, ?, ?, ?)
        """, (order_id, item.Busket_Product, quantity, price))

    # Очищаем корзину
    cursor.execute("DELETE FROM Busket WHERE Busket_User = ?", (user_id,))
    conn.commit()
    conn.close()

    # Формируем и отправляем письмо
    try:
        # Создаем HTML-содержимое письма
        html_content = f"""
        <h2>Новый заказ №{order_id}</h2>
        <table border="1" cellpadding="5" cellspacing="0">
            <tr>
                <th>Товар</th>
                <th>Цена</th>
                <th>Количество</th>
                <th>Сумма</th>
            </tr>
            {"".join(
                f"<tr><td>{item['name']}</td><td>{item['price']} руб.</td><td>{item['quantity']}</td><td>{item['total']} руб.</td></tr>"
                for item in order_details
            )}
            <tr>
                <td colspan="3"><strong>Итого:</strong></td>
                <td><strong>{total_amount} руб.</strong></td>
            </tr>
        </table>
        <p>ID пользователя: {user_id}</p>
        """

        msg = Message(
            subject=f"Новый заказ №{order_id}",
            recipients=["nikitalucenko2005@yandex.ru"],
            html=html_content
        )
        mail.send(msg)
    except Exception as e:
        print(f"Ошибка при отправке письма: {e}")

    flash('Спасибо за заказ!', 'popup')
    return redirect(url_for('profile'))

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