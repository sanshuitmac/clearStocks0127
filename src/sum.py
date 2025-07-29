import os

import pandas as pd  # excel处理库
from datetime import datetime
from pathlib import Path
import requests


def get_stock_price2(stock_code):
    if stock_code.startswith('6'):
        market_prefix = "sh"  # 沪市
    elif stock_code.startswith(('0', '3')):
        market_prefix = "sz"  # 深市
    elif stock_code.startswith('8'):
        market_prefix = "bj"  # 北交所
    else:
        print(f"未知股票代码格式: {stock_code}")
        return

    # 腾讯财经接口示例（沪市加前缀sh，深市加sz）
    url = f"http://qt.gtimg.cn/q={market_prefix}{stock_code}"
    response = requests.get(url)
    data = response.text
    # 解析价格，分隔字符串后第4个字段为当前价格
    try:
        # print(data)  # todo 查看返回值时打开
        code_part = data.split('="')[0].split('_')[-1]
        content = data.split('="')[1]
        values = content.split('~')
        stock_code = code_part[2:]  # 去除市场前缀
        stock_name = values[1]
        current_price = values[3]
    except (IndexError, ValueError):
        current_price = None
    return current_price


# github工作流和本地运行，产生的文件放在不同的目录。（gitignore忽略本地运行的目录的文件；工作流运行产生的文件不忽略，让其自动推送到仓库）
def create_output_directory():
    # 检查环境变量以确定当前的运行环境。github工作流产生文件放在workflow_files下
    if os.getenv('GITHUB_ACTIONS') == 'true':
        output_dir = 'files/workflow_files/'
    else:
        output_dir = 'files/local_files/'

    # 创建目录（如果不存在）
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    return output_dir


# 推送tg消息
def send_telegram_message(bot_token, chat_id, message):
    if not bot_token or not chat_id:
        print('没有配置tg机器人，无法推送')
        return
    tg_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": message
    }
    response = requests.post(tg_url, json=data)
    if response.status_code == 200:
        print("tg消息推送成功!")
    else:
        print("Failed to send tg message. Status code:", response.status_code)


if __name__ == '__main__':

    TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")  # 这里用了sanshui tg号机器人发送给yui号
    TG_CHAT_ID = os.getenv("TG_CHAT_ID")
    # Load the Excel file
    output_dir = create_output_directory()  # 区分工作流目录和本地运行目录（本地运行前记得github拉取）
    file_path = Path(__file__).parent / f"{output_dir}now_price8.xlsx"  # 工作流运行目录Path(__file__).parent ，即src目录
    # todo 默认会将数字格式的字符串（如 002495）识别为数字类型，而数字类型会忽略前导零。为了避免这个问题，需要确保股票代码以字符串形式读取和存储
    df = pd.read_excel(file_path, dtype={'代码': str})  # pandas读取excel，并且代码列，内容读取为str（否则002495会被读取成2495）
    # Show the first few rows to understand its structure
    df.head()
    # qingcang价格： 计算调仓是否正确
    investment_data = {
        "byd": {"cost": 92.53, "quantity": 900},  # 25.7.28 笛子拆股1拆3
        "ht": {"cost": 6.86, "quantity": 57400},
        "hy": {"cost": 13.87, "quantity": 11740},
        "hj": {"cost": 17.18, "quantity": 2300},
        "zh": {"cost": 40.8, "quantity": 3000},
        "mt": {"cost": 1435.89, "quantity": 100},
        "liuzi": {"cost": 10.12, "quantity": 2800},
        "sg_1": {"cost": 64.44, "quantity": 1600},
        "sg_2": {"cost": 64.25, "quantity": 1100},
    }

    # Create a mapping from the Excel's '票' to investment keys
    excel_to_investment_map = {
        "sg": ["sg_1", "sg_2"],
    }
    total_initial_cost = 0
    for stock, data in investment_data.items():
        total_initial_cost += data["cost"] * data["quantity"]
    print(f'成本：{total_initial_cost}')

    # 获取最新价格(腾讯财经)
    prices = []
    for code in df["代码"]:
        # print(code)
        # code = str(code).zfill(6)  # 深0开头，经常读取后去掉0，这里补0。上方已解决，读取时以字符串格式读取
        price = get_stock_price2(code)
        # print(price)
        prices.append(price)

    # 更新 DataFrame
    df["now价格"] = prices

    # 保存更新后的 Excel
    df.to_excel(file_path, index=False)
    print(f"\n已爬取腾讯财经最新价格，并保存到 {file_path}中")

    # Calculate total P&L  计算清仓/调仓后盈亏
    total_profit_loss = 0
    profit_loss = 0
    df = pd.read_excel(file_path)  # 需要再次读取，主要读取爬取下来的价格。ps上方价格列表已有，可以单独计算无需读取
    total_list  = []
    for _, row in df.iterrows():
        stock = row["票"]
        now_price = row["now价格"]

        # 多账号时，写在excel_to_investment_map，暂时只有一个 sg
        if stock in excel_to_investment_map:
            for investment_key in excel_to_investment_map[stock]:
                cost = investment_data[investment_key]["cost"]
                quantity = investment_data[investment_key]["quantity"]
                profit_loss = round((now_price - cost) * quantity, 2)
                total_profit_loss += profit_loss
                # print(investment_key, now_price, profit_loss)
                total_list.append(f'{investment_key},{now_price},{profit_loss}')
        elif stock in investment_data:
            cost = investment_data[stock]["cost"]
            quantity = investment_data[stock]["quantity"]
            profit_loss = round((now_price - cost) * quantity, 2)
            total_profit_loss += profit_loss
            # print(stock, now_price, profit_loss)
            total_list.append(f'{stock},{now_price},{profit_loss}')
    print(total_list)
    total_profit_loss = round(total_profit_loss, 2)  # 保留两位数
    current_date = datetime.now().date()
    msg = f'\n{total_list}。\n如果2025年1月27不调仓，则至{current_date}日，盈亏为：{total_profit_loss}'
    send_telegram_message(TG_BOT_TOKEN, TG_CHAT_ID, msg)
    print(f'\n如果2025年1月27不调仓，则至{current_date}日，盈亏为：{total_profit_loss}')

