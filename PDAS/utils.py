import random
import string
import bcrypt

def hash_password(password):
    """
    使用 bcrypt 加密密码
    """
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(password, hashed_password):
    """
    验证输入密码是否匹配加密密码
    """
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))

def generate_dynamic_password(password):
    """
    根据用户输入的密码生成动态密码。
    - 提取密码的前 8 位并打乱顺序。
    - 在末尾添加 4 位随机盐值。
    :param password: 用户输入的原始密码（至少 8 位）
    :return: 动态密码（长度为 12 位）
    """
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long.")

    # 提取前 8 位并打乱顺序
    shuffled_password = ''.join(random.sample(password[:8], len(password[:8])))

    # 生成 4 位随机盐值
    salt = ''.join(random.choices(string.ascii_letters + string.digits, k=4))

    # 拼接动态密码
    dynamic_password = shuffled_password + salt

    return dynamic_password

