from datetime import date
from flask import Flask, render_template, redirect, url_for, flash, request, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_ckeditor import CKEditor
from flask_bootstrap import Bootstrap
from flask_gravatar import Gravatar
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, text
from functools import wraps
import os
import stripe
from dotenv import load_dotenv
load_dotenv()
from forms import AddProductForm, LoginForm, RegisterForm


# --- App Config ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("FLASK_SECRET_KEY")
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///my_works.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- Stripe Config ---
stripe.api_key = os.getenv("STRIPE_API_KEY")

ckeditor = CKEditor(app)
Bootstrap(app)

# --- Login Manager ---
login_manager = LoginManager()
login_manager.init_app(app)

# --- Gravatar for comments (optional) ---
gravatar = Gravatar(app, size=100, rating='g', default='retro')

# --- DB Config ---
class Base(DeclarativeBase): pass
db = SQLAlchemy(model_class=Base)
db.init_app(app)

# --- MODELS ---
class Users(UserMixin, db.Model):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    products = relationship("ProductPosts", back_populates="user")

class ProductPosts(db.Model):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    price: Mapped[str] = mapped_column(String(20), nullable=False)
    delivery: Mapped[str] = mapped_column(String(250), nullable=False)
    image_path: Mapped[str] = mapped_column(String(250), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, db.ForeignKey('users.id'))
    user = relationship('Users', back_populates='products')
    cart_items = relationship('CartItem',back_populates = 'product', cascade = 'all, delete-orphan')
class CartItem(db.Model):
    __tablename__ = "cart_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(Integer, db.ForeignKey('products.id'), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, db.ForeignKey('users.id'), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    product = relationship('ProductPosts', back_populates = 'cart_items')
    user = relationship('Users')

with app.app_context():
    db.create_all()

# --- Admin Decorator ---
def admin_only(function):
    @wraps(function)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.id != 1:
            return abort(403)
        return function(*args, **kwargs)
    return decorated

# --- Context Processor for Cart Count ---
@app.context_processor
def cart_count_processor():
    count = 0
    if current_user.is_authenticated:
        count = sum(item.quantity for item in CartItem.query.filter_by(user_id=current_user.id).all())
    return dict(cart_count=count)

# --- Flask-Login Loader ---
@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(Users, user_id)

# --- ROUTES ---

@app.route('/')
def home():
    products = db.session.execute(db.select(ProductPosts)).scalars().all()
    return render_template("home.html", all_products=products, current_user=current_user)

@app.route('/register', methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        if db.session.execute(db.select(Users).where(Users.email == form.email.data)).scalar():
            flash("You've already signed up with that email, login instead!")
            return redirect(url_for('login'))
        hashed_pw = generate_password_hash(form.password.data, method='pbkdf2:sha256', salt_length=8)
        new_user = Users(email=form.email.data, password=hashed_pw, name=form.name.data)
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for('home'))
    return render_template("register.html", form=form, current_user=current_user)

@app.route('/login', methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.execute(db.select(Users).where(Users.email == form.email.data)).scalar()
        if not user:
            flash("That email does not exist.")
            return redirect(url_for("login"))
        elif not check_password_hash(user.password, form.password.data):
            flash("Password incorrect.")
            return redirect(url_for("login"))
        login_user(user)
        return redirect(url_for('home'))
    return render_template("login.html", form=form, current_user=current_user, page_title = "Login")

@app.route('/logout')
@login_required
def logout():
    # Delete cart items using db.session.execute() without using text()
    db.session.execute(
        text("DELETE FROM cart_items WHERE user_id = :user_id"),
        {"user_id": current_user.id}
    )
    db.session.commit()
    logout_user()
    flash("You have been logged out and your cart has been cleared.", "info")
    return redirect(url_for('home'))

@app.route("/product/<int:product_id>")
def show_product(product_id):
    product = db.get_or_404(ProductPosts, product_id)
    return render_template("products.html", product=product, current_user=current_user)

@app.route('/add-product', methods=['GET', 'POST'])
@admin_only
def add_product():
    form = AddProductForm()
    if form.validate_on_submit():
        file = form.image_path.data
        filename = secure_filename(file.filename)
        path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(path)
        new_product = ProductPosts(
            title=form.title.data,
            price=form.price.data,
            delivery=form.delivery.data,
            image_path=path,
            user_id=current_user.id
        )
        db.session.add(new_product)
        db.session.commit()
        return redirect(url_for('home'))
    return render_template("products.html", form=form, product=None)

@app.route('/edit-product/<int:product_id>', methods=['GET', 'POST'])
@admin_only
def edit_product(product_id):
    product = db.get_or_404(ProductPosts, product_id)
    form = AddProductForm(obj=product)
    if form.validate_on_submit():
        if form.image.data:
            file = form.image.data
            filename = secure_filename(file.filename)
            path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(path)
            product.image_path = path
        product.title = form.title.data
        product.price = form.price.data
        product.delivery = form.delivery.data
        db.session.commit()
        return redirect(url_for('home'))
    return render_template("products.html", form=form, product=product)

@app.route('/delete-product/<int:product_id>')
@admin_only
def delete_product(product_id):
    product = db.get_or_404(ProductPosts, product_id)
    db.session.delete(product)
    db.session.commit()
    return redirect(url_for('home'))

@app.route('/add-to-cart/<int:product_id>')
@login_required
def add_to_cart(product_id):
    item = CartItem.query.filter_by(user_id=current_user.id, product_id=product_id).first()
    if item:
        item.quantity += 1
    else:
        item = CartItem(user_id=current_user.id, product_id=product_id, quantity=1)
        db.session.add(item)
    db.session.commit()
    flash("Added to cart!")
    return redirect(url_for('home'))

@app.route('/view-cart')
@login_required
def view_cart():
    items = CartItem.query.filter_by(user_id=current_user.id).all()
    total = sum(float(item.product.price) * item.quantity for item in items)
    return render_template("cart.html", items=items, total=total)

@app.route('/services')
def our_services():
    return render_template("services.html")

@app.route("/about")
def about_ecommerce():
    return render_template('about.html', current_user=current_user)

@app.route("/contact")
def contact_us():
    return render_template("contact.html", current_user=current_user, page_title = "Contact IwayEnate")

@app.route('/create-checkout-session', methods=['POST'])
@login_required
def create_checkout_session():
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()

    if not cart_items:
        flash("Your cart is empty.")
        return redirect(url_for('view_cart'))

    line_items = []
    for item in cart_items:
        line_items.append({
            'price_data': {
                'currency': 'usd',
                'unit_amount': int(float(item.product.price) * 100),  # Stripe uses cents
                'product_data': {
                    'name': item.product.title,
                },
            },
            'quantity': item.quantity,
        })

    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=line_items,
            mode='payment',
            success_url=url_for('success', _external=True),
            cancel_url=url_for('cancel', _external=True),
            customer_email=current_user.email
        )
        return redirect(checkout_session.url, code=303)

    except Exception as e:
        print(f"Stripe Checkout Error: {e}")
        return str(e)
@app.route('/success')
def success():
    # Clear cart after successful payment
    if current_user.is_authenticated:
        CartItem.query.filter_by(user_id=current_user.id).delete()
        db.session.commit()
    return render_template('success.html')

@app.route('/cancel')
def cancel():
    flash("Payment was cancelled.")
    return redirect(url_for('view_cart'))

# --- Run App ---
if __name__ == '__main__':
    app.run(debug=True, port = 5000)

