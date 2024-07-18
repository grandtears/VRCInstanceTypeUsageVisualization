# 必要なライブラリのインポート
import matplotlib.pyplot as plt
import numpy as np
import re
from datetime import datetime, timedelta
from collections import defaultdict
import os

#pip install numpy
#pip install matplotlib が必要

# 日本語フォントの設定
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.sans-serif'] = ['Hiragino Sans', 'Yu Gothic', 'Meirio', 'Takao', 'IPAexGothic', 'IPAPGothic', 'VL PGothic', 'Noto Sans CJK JP']

def determine_instance_type(instance_id):
    # インスタンスIDからインスタンスタイプを判定する関数
    print(instance_id)
    if '~hidden' in instance_id:
        return 'FRIEND_PLUS'
    if '~friends' in instance_id:
        return 'FRIEND'
    if '~private' in instance_id and '~canRequestInvite' in instance_id:
        return 'INVITE_PLUS'
    if '~private' in instance_id and '~canRequestInvite' not in instance_id:
        return 'INVITE'
    if '~group' in instance_id and '~groupAccessType(members)' in instance_id:
        return 'GROUP'
    if '~group' in instance_id and '~groupAccessType(plus)' in instance_id:
        return 'GROUP_PLUS'
    if '~group' in instance_id and '~groupAccessType(public)' in instance_id:
        return 'GROUP_PUBLIC'
    return 'PUBLIC'  # どの条件にも当てはまらない場合はPUBLIC

def parse_log_file(file_path):
    # ログファイルを解析し、インスタンスタイプとワールドごとの滞在時間と訪問回数を計算する関数
    instance_times = defaultdict(lambda: {'total': timedelta(), 'last_join': None})
    world_times = defaultdict(timedelta)
    world_visits = defaultdict(int)
    
    # 正規表現パターンの定義
    # ワールドIDとインスタンスタイプ
    join_pattern = r'(\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2}) Log.*\[Behaviour\] Joining (wrld_[^:]+:[^\~]+\~(?:hidden|friends|private|group)[^\r\n]+)'
    # ワールド名
    create_pattern = r'(\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2}) Log.*\[Behaviour\] Joining or Creating Room: (.+)'
    # Leftワールド
    leave_pattern = r'(\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2}) Log.*\[Behaviour\] OnLeftRoom'
    
    current_instance_type = None
    current_world_name = None
    
    # 最初と最後の日付を追跡
    first_date = None
    last_date = None
    
    # ログファイルの読み込み
    with open(file_path, 'r', encoding='utf-8') as file:
        log_content = file.read()
    
    # イベントの抽出とソート
    # タイムスタンプでソート
    events = sorted(
        list(re.finditer(join_pattern, log_content, re.MULTILINE)) +
        list(re.finditer(create_pattern, log_content, re.MULTILINE)) +
        list(re.finditer(leave_pattern, log_content, re.MULTILINE)),
        key=lambda x: x.group(1)
    )
    
    # イベントの処理
    for event in events:
        timestamp = datetime.strptime(event.group(1), '%Y.%m.%d %H:%M:%S')
        
        # 最初の日付を設定
        if first_date is None:
            first_date = timestamp.date()
        # 最後の日付を更新
        last_date = timestamp.date()
        
        if 'Joining ' in event.group(0) and 'Joining or Creating Room:' not in event.group(0):
            # インスタンス参加イベントの処理
            if current_instance_type:
                # 前のインスタンスの滞在時間を計算
                if instance_times[current_instance_type]['last_join']:
                    duration = timestamp - instance_times[current_instance_type]['last_join']
                    instance_times[current_instance_type]['total'] += duration
                    world_times[current_world_name] += duration
            
            current_instance_type = determine_instance_type(event.group(2))
            instance_times[current_instance_type]['last_join'] = timestamp
        
        elif 'Joining or Creating Room:' in event.group(0):
            # ワールド参加イベントの処理
            current_world_name = event.group(2)
            world_visits[current_world_name] += 1  # 訪問回数をカウント
        
        elif 'OnLeftRoom' in event.group(0):
            # ワールド退出イベントの処理
            if current_instance_type:
                if instance_times[current_instance_type]['last_join']:
                    duration = timestamp - instance_times[current_instance_type]['last_join']
                    instance_times[current_instance_type]['total'] += duration
                    world_times[current_world_name] += duration
                    instance_times[current_instance_type]['last_join'] = None
                current_instance_type = None
                current_world_name = None
    
    # 最後のインスタンスの滞在時間を計算（ログの最後がLeaveでない場合）
    if current_instance_type and instance_times[current_instance_type]['last_join']:
        last_timestamp = datetime.strptime(events[-1].group(1), '%Y.%m.%d %H:%M:%S')
        duration = last_timestamp - instance_times[current_instance_type]['last_join']
        instance_times[current_instance_type]['total'] += duration
        world_times[current_world_name] += duration
    
    # 有効なログエントリが見つからなかった場合の処理
    if first_date is None or last_date is None:
        print(f"警告: ファイル {file_path} に有効なログエントリが見つかりませんでした。")
        return {}, {}, {}, (None, None)
    
    # 時間単位（時）で結果を返す
    return {k: v['total'].total_seconds() / 3600 for k, v in instance_times.items()}, \
           {k: v.total_seconds() / 3600 for k, v in world_times.items()}, \
           dict(world_visits), \
           (first_date, last_date)

def process_log_folder(folder_path):
    # 指定されたフォルダ内のすべてのログファイルを処理する関数
    total_instance_times = defaultdict(float)
    total_world_times = defaultdict(float)
    total_world_visits = defaultdict(int)
    log_file_pattern = r'output_log_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}\.txt'
    
    first_date = None
    last_date = None
    
    for filename in os.listdir(folder_path):
        if re.match(log_file_pattern, filename):
            file_path = os.path.join(folder_path, filename)
            file_instance_times, file_world_times, file_world_visits, (file_first_date, file_last_date) = parse_log_file(file_path)
            
            # ファイルに有効なデータがある場合のみ処理
            if file_first_date is not None and file_last_date is not None:
                # 各ファイルの結果を合算
                for instance_type, duration in file_instance_times.items():
                    total_instance_times[instance_type] += duration
                for world_name, duration in file_world_times.items():
                    total_world_times[world_name] += duration
                for world_name, visits in file_world_visits.items():
                    total_world_visits[world_name] += visits
                
                # 全体の日付範囲を更新
                if first_date is None or file_first_date < first_date:
                    first_date = file_first_date
                if last_date is None or file_last_date > last_date:
                    last_date = file_last_date
    
    if first_date is None or last_date is None:
        print("警告: 処理可能なログファイルが見つかりませんでした。")
        return {}, {}, {}, (None, None)
    
    return dict(total_instance_times), dict(total_world_times), dict(total_world_visits), (first_date, last_date)

def create_charts(instance_times, world_times, world_visits, date_range):
    # グラフを作成する関数
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(20, 20))
    fig.suptitle(f'VRCインスタンスタイプとワールドの滞在時間・訪問回数分析\n期間: {date_range[0]} から {date_range[1]}', fontsize=16, y=0.95)
    
    # インスタンスタイプの円グラフ
    labels = list(instance_times.keys())
    sizes = list(instance_times.values())
    total_hours = sum(sizes)
    ax1.pie(sizes, labels=labels, autopct=lambda pct: f'{pct:.1f}%\n({pct*total_hours/100:.1f}時間)', startangle=90)
    ax1.axis('equal')
    ax1.set_title('インスタンスタイプ別滞在時間割合', fontsize=14, pad=20)
    
    # インスタンスタイプの棒グラフ
    colors = plt.cm.Set3(np.linspace(0, 1, len(labels)))
    ax2.bar(labels, sizes, color=colors)
    ax2.set_ylabel('滞在時間 (時間)', fontsize=12)
    ax2.set_title('インスタンスタイプ別滞在時間', fontsize=14, pad=20)
    for i, v in enumerate(sizes):
        ax2.text(i, v, f'{v:.1f}', ha='center', va='bottom')
    plt.setp(ax2.get_xticklabels(), rotation=45, ha='right')
    
    # トップ10ワールドの滞在時間棒グラフ
    top_worlds_time = sorted(world_times.items(), key=lambda x: x[1], reverse=True)[:10]
    world_names_time, world_durations = zip(*top_worlds_time)
    ax3.bar(world_names_time, world_durations)
    ax3.set_ylabel('滞在時間 (時間)', fontsize=12)
    ax3.set_title('滞在時間トップ10ワールド', fontsize=14, pad=20)
    for i, v in enumerate(world_durations):
        ax3.text(i, v, f'{v:.1f}', ha='center', va='bottom')
    plt.setp(ax3.get_xticklabels(), rotation=90, ha='right')
    
    # トップ10ワールドの訪問回数棒グラフ
    top_worlds_visits = sorted(world_visits.items(), key=lambda x: x[1], reverse=True)[:10]
    world_names_visits, visit_counts = zip(*top_worlds_visits)
    ax4.bar(world_names_visits, visit_counts)
    ax4.set_ylabel('訪問回数', fontsize=12)
    ax4.set_title('訪問回数トップ10ワールド', fontsize=14, pad=20)
    for i, v in enumerate(visit_counts):
        ax4.text(i, v, str(v), ha='center', va='bottom')
    plt.setp(ax4.get_xticklabels(), rotation=90, ha='right')
    
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    plt.show()

# メイン処理
log_folder_path = 'C:\\Develop\\Logs'  # VRCのログフォルダへのパスを指定してください
instance_times, world_times, world_visits, date_range = process_log_folder(log_folder_path)

if date_range[0] is None or date_range[1] is None:
    print("エラー: 有効なログデータが見つかりませんでした。プログラムを終了します。")
else:
    create_charts(instance_times, world_times, world_visits, date_range)
    print(f"ログの期間: {date_range[0]} から {date_range[1]}")