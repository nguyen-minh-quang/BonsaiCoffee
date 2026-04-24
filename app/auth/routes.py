from functools import wraps

from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user

from app import db
from app.models import User, ShopSetting

auth_bp = Blueprint('auth', __name__)


def role_required(role):
    """Decorator kiểm tra phân quyền. Admin có thể truy cập tất cả routes."""
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            if current_user.role == 'admin':
                return f(*args, **kwargs)
            if current_user.role != role:
                flash('Bạn không có quyền truy cập trang này.', 'danger')
                return redirect(url_for('auth.login'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def redirect_by_role(user):
    """Redirect người dùng theo role."""
    if user.role == 'admin':
        return redirect('/admin/')
    elif user.role == 'cashier':
        return redirect('/cashier/')
    elif user.role == 'waiter':
        return redirect('/waiter/')
    return redirect(url_for('auth.login'))


@auth_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect_by_role(current_user)
    return redirect(url_for('auth.login'))


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect_by_role(current_user)

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user)
            return redirect_by_role(user)
        else:
            flash('Sai tên đăng nhập hoặc mật khẩu.', 'danger')

    return render_template('auth/login.html')


@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        old_pw = request.form.get('old_password', '')
        new_pw = request.form.get('new_password', '')
        confirm_pw = request.form.get('confirm_password', '')

        if not current_user.check_password(old_pw):
            flash('Mật khẩu cũ không đúng.', 'error')
        elif len(new_pw) < 4:
            flash('Mật khẩu mới phải ít nhất 4 ký tự.', 'error')
        elif new_pw != confirm_pw:
            flash('Xác nhận mật khẩu không khớp.', 'error')
        else:
            current_user.set_password(new_pw)
            db.session.commit()
            flash('Đổi mật khẩu thành công!', 'success')
            return redirect(url_for('auth.change_password'))

    return render_template('auth/change_password.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))
