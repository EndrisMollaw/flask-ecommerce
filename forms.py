from flask_ckeditor import CKEditorField
from flask_wtf import FlaskForm

from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import StringField, SubmitField, PasswordField
from wtforms.validators import DataRequired

class AddProductForm(FlaskForm):
    image_path = FileField("Product Image", validators = [FileRequired(), FileAllowed(['jpg', 'jpeg', 'png', 'webp', 'avif'], 'Images only!')])
    title = StringField("Title", validators = [DataRequired()])
    price = StringField("Price", validators = [DataRequired()])
    delivery = StringField("Delivery Info", validators = [DataRequired()])
    submit = SubmitField("Add Product")
#Create a form to login existing users
class LoginForm(FlaskForm):
    email = StringField("Email", validators = [DataRequired()])
    password = PasswordField("Password", validators = [DataRequired()])
    submit = SubmitField("Login")

#Create a form to register new users
class RegisterForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    name = StringField("Name", validators=[DataRequired()])
    submit = SubmitField("Sign Up")
#Create a form to comment on products
class CommentForm(FlaskForm):
    comment_text = CKEditorField("Comment", validators=[DataRequired()])
    submit = SubmitField("Submit Comment")