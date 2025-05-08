import os
import json
import sys
# 确保能导入 app.py 中的函数 (如果 app.py 在根目录)
# 如果目录结构不同，调整 sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR) 

try:
    # 尝试从 app.py 导入需要的函数和路径
    from app import USERS_DIR, FAVORITES_COUNT_PATH, get_user_data, save_favorites_count, app
except ImportError as e:
    print(f"导入 app.py 中的函数或变量失败: {e}")
    print("请确保此脚本与 app.py 在同一层级，或者调整 sys.path。")
    sys.exit(1)
except Exception as e:
    print(f"初始化脚本时发生错误: {e}")
    sys.exit(1)

def calculate_all_favorites():
    """遍历所有用户文件，统计每个学校的总收藏次数。"""
    print("开始计算所有用户的收藏...")
    total_favorites_count = {}
    if not os.path.exists(USERS_DIR):
        print(f"用户数据目录 {USERS_DIR} 不存在。无法计算收藏。")
        return total_favorites_count 

    user_files = [f for f in os.listdir(USERS_DIR) if f.endswith(".json")]
    print(f"找到 {len(user_files)} 个用户文件。")

    processed_users = 0
    for filename in user_files:
        username = filename[:-5] 
        user_data = get_user_data(username) # 使用 app.py 中的函数读取
        if user_data and isinstance(user_data.get('favorites'), list):
            processed_users += 1
            for school_id in user_data['favorites']:
                total_favorites_count[school_id] = total_favorites_count.get(school_id, 0) + 1
        elif user_data is None:
             print(f"警告：无法加载用户数据: {username}")
        # else: 用户数据格式不正确或没有 favorites 列表
    
    print(f"处理了 {processed_users} 个用户的收藏数据。")
    print(f"计算得到的总收藏数: {total_favorites_count}")
    return total_favorites_count

if __name__ == "__main__":
    print(f"将把计算结果保存到: {FAVORITES_COUNT_PATH}")
    calculated_counts = calculate_all_favorites()
    
    if not calculated_counts:
         print("没有计算到任何收藏数据，将写入空文件。")
         
    if save_favorites_count(calculated_counts): # 使用 app.py 中的函数保存
        print("成功初始化/更新 favorites_count.json 文件！")
    else:
        print("错误：保存 favorites_count.json 文件失败！") 