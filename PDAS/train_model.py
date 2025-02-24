import numpy as np
import sqlite3
import tensorflow as tf
import pickle

# 从数据库提取密码
def extract_passwords_from_db():
    conn = sqlite3.connect('pdas.db')  # 替换为你自己的数据库路径
    cursor = conn.cursor()
    
    cursor.execute("SELECT password FROM users")  # 假设密码字段名为 'password'
    rows = cursor.fetchall()
    
    passwords = [row[0].decode('utf-8') if isinstance(row[0], bytes) else row[0] for row in rows]
    
    conn.close()
    return passwords

# 准备数据
def prepare_data(passwords, seq_length=10):
    # 创建字符映射字典
    chars = sorted(list(set(''.join(passwords))))
    char_to_int = {char: index for index, char in enumerate(chars)}
    int_to_char = {index: char for index, char in enumerate(chars)}

    # 创建训练序列和目标字符
    sequences = []
    next_chars = []

    for password in passwords:
        for i in range(len(password) - seq_length):
            sequences.append([char_to_int[char] for char in password[i:i+seq_length]])
            next_chars.append(char_to_int[password[i+seq_length]])

    # 转换为 numpy 数组并进行归一化处理
    X = np.array(sequences)
    y = np.array(next_chars)

    # 归一化输入数据
    X = X / float(len(chars))  # 对字符索引进行归一化

    # 重塑 X 以适应 LSTM 输入要求 (样本数, 时间步数, 特征数)
    X = np.reshape(X, (X.shape[0], X.shape[1], 1))

    # 将目标数据转换为独热编码格式
    y = tf.keras.utils.to_categorical(y, num_classes=len(chars))

    return X, y, int_to_char, char_to_int

# 保存字典到文件
def save_char_mappings(char_to_int, int_to_char):
    with open('char_to_int.pkl', 'wb') as f:
        pickle.dump(char_to_int, f)
    with open('int_to_char.pkl', 'wb') as f:
        pickle.dump(int_to_char, f)

# 创建并训练 LSTM 模型
def create_and_train_model(X, y, int_to_char, char_to_int):
    # 创建 LSTM 模型
    model = tf.keras.models.Sequential([
        tf.keras.layers.LSTM(128, input_shape=(X.shape[1], 1), return_sequences=True),  # LSTM层
        tf.keras.layers.LSTM(128),  # 第二个 LSTM 层
        tf.keras.layers.Dense(64, activation='relu'),  # 全连接层
        tf.keras.layers.Dense(len(char_to_int), activation='softmax')  # 输出层
    ])

    # 编译模型
    model.compile(loss='categorical_crossentropy', optimizer='adam')

    # 训练模型
    model.fit(X, y, epochs=50, batch_size=64)

    # 保存模型
    model.save('password_model.h5')
    print("Model training complete and saved as 'password_model.h5'")

    # 保存字典
    save_char_mappings(char_to_int, int_to_char)
    print("Character mappings saved as 'char_to_int.pkl' and 'int_to_char.pkl'")

if __name__ == "__main__":
    # 步骤 1: 从数据库中提取密码
    passwords = extract_passwords_from_db()

    # 步骤 2: 准备数据
    X, y, int_to_char, char_to_int = prepare_data(passwords)

    # 步骤 3: 创建并训练 LSTM 模型
    create_and_train_model(X, y, int_to_char, char_to_int)
