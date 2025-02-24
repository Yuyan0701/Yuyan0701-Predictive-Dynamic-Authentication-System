import random
import string

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
