import json
import math
import os
import requests

from collections import defaultdict
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()
SLACK_TOKEN = os.getenv('SLACK_TOKEN')
SLACK_CHANNEL = os.getenv('SLACK_CHANNEL')
SLACK_LOG_CHANNEL = 'C08SZDPGSRX'

SLACK_WEBHOOK_URL = 'https://slack.com/api/chat.postMessage'

CREATED_FIXTURE = "\"Status\":201"
CREATE_PROFILE_PREFIX = '{"Reply":{"Method":"POST /api/profiles - '
ISSUE_TICKET_PREFIX = 'INFO com.yourssu.signal.infrastructure.Notification - Issued ticket'
RETRY_ISSUE_TICKET_PREFIX = 'INFO com.yourssu.signal.infrastructure.Notification - RetryIssuedTicket'
CONSUME_TICKET_PREFIX = 'INFO com.yourssu.signal.infrastructure.Notification - Consumed ticket'

CREATE_PROFILE_KEY = "createProfile"
CONSUMED_TICKET_KEY = "consumedTicket"
ISSUED_TICKET_KEY = "issuedTicket"


def get_recent_log_lines(hours) -> list:
    now = datetime.now()
    time_threshold = now - timedelta(hours=hours)
    recent_lines = []

    date_list = []
    current_date = time_threshold.date()
    while current_date <= now.date():
        date_list.append(current_date.strftime('%Y-%m-%d'))
        current_date += timedelta(days=1)
    directories = [f'logs/{date}/' for date in date_list]

    for directory in directories:
        if not os.path.exists(directory):
            continue

        for filename in os.listdir(directory):
            if filename.endswith('.log'):
                filepath = os.path.join(directory, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as file:
                        for line in file:
                            try:
                                timestamp_str = ' '.join(line.split(' ')[:2])
                                log_time = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S.%f')
                                if log_time >= time_threshold:
                                    recent_lines.append(line.strip())
                            except Exception:
                                continue
                except Exception as e:
                    print(f"파일 열기 실패: {filepath}, 에러: {e}")
    return recent_lines


def count_ip_addresses(log_lines) -> int:
    ips = set()
    for line in log_lines:
        try:
            json_str = line.split(' - ', 1)[1].strip()
            data = json.loads(json_str)
            x_real_ip = data.get('Request', {}).get('Headers', {}).get('x-real-ip')
            if x_real_ip:
                ips.add(x_real_ip)
        except Exception:
            continue
    return len(ips)


def create_count_visitor_message(hours) -> int:
    recent_log_lines = get_recent_log_lines(hours)
    return count_ip_addresses(recent_log_lines)


def create_analysis_message(hours, visitor_count, profile_count, issued_ticket_count, consume_ticket_count) -> str:
    return f""" *💌 시그널 최근 {hours} 시간 분석 보고서 💌*
    - *📅  분석 기간* : {(datetime.now() - timedelta(hours=hours)).strftime('%Y년 %m월 %d일 %H시 %M분')} ~ {datetime.now().strftime('%Y년 %m월 %d일 %H시 %M분')}
    - *👥  방문자 수* : {visitor_count} 명
    - *👤 등록한 프로필* : {profile_count} 개
    - *🎁  발급한 이용권* : {issued_ticket_count} 개
    - *💌  사용한 이용권* : {consume_ticket_count} 개
"""


def get_created_profile(line, dic):
    if CREATED_FIXTURE in line:
        dic[CREATE_PROFILE_KEY] += 1


def get_issued_ticket(line, dic):
    verification, uuid, ticket, available_ticket = line[line.find('&') + 1:].split(' ')
    dic[ISSUED_TICKET_KEY] += int(ticket)


def get_ticket_by_bank_deposit(line, dic):
    verification, uuid, ticket, available_ticket, name = line[line.find('&') + 1:].split(' ')
    dic[ISSUED_TICKET_KEY] += int(ticket)


def get_consumed_ticket_message(line, dic):
    dic[CONSUMED_TICKET_KEY] += 1


handler = {
    CREATE_PROFILE_PREFIX: get_created_profile,
    ISSUE_TICKET_PREFIX: get_issued_ticket,
    RETRY_ISSUE_TICKET_PREFIX: get_ticket_by_bank_deposit,
    CONSUME_TICKET_PREFIX: get_consumed_ticket_message,
}


def send_slack_notification(message):
    payload = {
        'channel': SLACK_CHANNEL,
        'text': message
    }
    headers = {
        'Authorization': f'Bearer {SLACK_TOKEN}',
        'Content-Type': 'application/json'
    }
    log = requests.post(SLACK_WEBHOOK_URL, json=payload, headers=headers)
    print(log.text)


def send_slack_log_notification(message):
    payload = {
        'channel': SLACK_LOG_CHANNEL,
        'text': message
    }
    headers = {
        'Authorization': f'Bearer {SLACK_TOKEN}',
        'Content-Type': 'application/json'
    }
    log = requests.post(SLACK_WEBHOOK_URL, json=payload, headers=headers)
    print(log.text)


def run(hours=1):
    dic = defaultdict(int)
    for line in get_recent_log_lines(hours):
        for prefix, handler_func in handler.items():
            if prefix in line:
                try:
                    handler_func(line, dic)
                except Exception:
                    continue
    visitor_count = create_count_visitor_message(hours)
    profile_count = dic[CREATE_PROFILE_KEY]
    issued_ticket_count = dic[ISSUED_TICKET_KEY]
    consume_ticket_count = dic[CONSUMED_TICKET_KEY]
    message = create_analysis_message(hours=hours,
                                      visitor_count=visitor_count,
                                      profile_count=profile_count,
                                      issued_ticket_count=issued_ticket_count,
                                      consume_ticket_count=consume_ticket_count)
    # send_slack_notification(message)
    print(message)


def get_total_hours(date_str, date_format="%Y-%m-%d %H:%M"):
    past_time = datetime.strptime(date_str, date_format)
    now = datetime.now()
    diff = now - past_time
    total_hours = diff.total_seconds() / 3600
    return math.ceil(total_hours)


if __name__ == "__main__":
    # hours = get_total_hours("2025-05-18 00:00")
    hours = 1
    run(hours)
