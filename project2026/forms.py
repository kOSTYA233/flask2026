from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import (
    BooleanField, PasswordField, StringField,
    SubmitField, TextAreaField, SelectField, DateField,
)
from wtforms.validators import DataRequired, EqualTo, Length, Regexp, Optional

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "pdf", "txt", "doc", "docx", "zip"}


class SignInForm(FlaskForm):
    username = StringField("Логин", validators=[DataRequired(), Length(min=3, max=50)])
    password = PasswordField("Пароль", validators=[DataRequired()])
    submit = SubmitField("Войти")


class NewAccountForm(FlaskForm):
    username = StringField(
        "Логин нового пользователя",
        validators=[
            DataRequired(),
            Length(min=3, max=50),
            Regexp(r"^[A-Za-z0-9_.-]+$", message="Только буквы, цифры, _, . и -"),
        ],
    )
    password = PasswordField("Пароль", validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField(
        "Подтверждение пароля",
        validators=[DataRequired(), EqualTo("password", message="Пароли не совпадают.")],
    )
    is_admin = BooleanField("Права администратора")
    submit = SubmitField("Создать")


class TaskForm(FlaskForm):
    title = StringField("Название", validators=[DataRequired(), Length(min=3, max=200)])
    description = TextAreaField("Описание", validators=[DataRequired(), Length(min=5)])
    priority = SelectField(
        "Приоритет",
        choices=[("high", "Высокий"), ("medium", "Средний"), ("low", "Низкий")],
        default="medium",
    )
    deadline = DateField("Дедлайн", validators=[Optional()])
    is_private = BooleanField("Приватная задача")
    attachment = FileField("Прикрепить файл", validators=[FileAllowed(list(ALLOWED_EXTENSIONS))])
    submit = SubmitField("Сохранить")


class StatusForm(FlaskForm):
    status = SelectField(
        "Статус",
        choices=[
            ("new", "Новый"),
            ("in_progress", "В разработке"),
            ("done", "Готово"),
            ("archived", "В архиве"),
        ],
    )
    submit = SubmitField("Обновить статус")


class CommentForm(FlaskForm):
    text = TextAreaField("Комментарий", validators=[DataRequired(), Length(min=1)])
    attachment = FileField("Прикрепить файл", validators=[FileAllowed(list(ALLOWED_EXTENSIONS))])
    submit = SubmitField("Отправить")
