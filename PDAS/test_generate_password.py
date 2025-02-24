import tensorflow as tf
import pickle
import numpy as np
import random

# 模型加载部分
try:
    model = tf.keras.models.load_model('password_model.h5')
    with open('char_to_int.pkl', 'rb') as f:
        char_to_int = pickle.load(f)
    with open('int_to_char.pkl', 'rb') as f:
        int_to_char = pickle.load(f)
    print("Model and mappings loaded successfully")
except Exception as e:
    print(f"Error loading model or mappings: {str(e)}")
    char_to_int = {str(i): i for i in range(10)}
    int_to_char = {i: str(i) for i in range(10)}

    print("char_to_int:", char_to_int)
print("int_to_char:", int_to_char)


# 密码生成函数
def generate_password(seed, model, char_to_int, int_to_char, length=12):
    password = ''
    
    # Ensure seed is valid and contains characters from char_to_int mapping
    for char in seed:
        if char not in char_to_int:
            raise ValueError(f"Character '{char}' in seed not found in char_to_int mapping.")
    
    for _ in range(length):
        # Convert seed to integer representation
        seed_int = [char_to_int[char] for char in seed]
        
        # Model expects a 3D input for LSTM (batch_size, timesteps, features)
        seed_int = np.array([seed_int])  # Add batch dimension
        
        # Predict the next character
        next_int = model.predict(seed_int, verbose=0)[0]
        
        print(f"Predicted next character probabilities: {next_int}")
        # Get the character corresponding to the predicted value
        next_char = int_to_char[np.argmax(next_int)]
        password += next_char
        
        # Update the seed for the next prediction (sliding window of characters)
        seed = seed[1:] + next_char

    return password

def generate_password_with_temperature(seed, model, char_to_int, int_to_char, length=12, temperature=1.0):
    password = ''
    
    for char in seed:
        if char not in char_to_int:
            raise ValueError(f"Character '{char}' in seed not found in char_to_int mapping.")
    
    for _ in range(length):
        seed_int = [char_to_int[char] for char in seed]
        seed_int = np.array([seed_int])  # Add batch dimension
        
        next_probs = model.predict(seed_int, verbose=0)[0]
        
        # Apply temperature
        next_probs = np.exp(next_probs / temperature)  # Scale the logits
        next_probs = next_probs / np.sum(next_probs)  # Normalize to get probabilities
        
        next_char_idx = np.random.choice(len(next_probs), p=next_probs)  # Sample from the probability distribution
        next_char = int_to_char[next_char_idx]
        password += next_char
        
        # Update seed
        seed = seed[1:] + next_char

    return password

# 测试种子生成密码
test_seed = 'abc'  # 用一个简单的种子
generated_password = generate_password_with_temperature(test_seed, model, char_to_int, int_to_char, length=12, temperature=0.8)
print(f"Generated Password: {generated_password}")


print("char_to_int:", char_to_int)
print("int_to_char:", int_to_char)
