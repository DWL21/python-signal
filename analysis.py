import json
import os
import requests

from collections import defaultdict
from dotenv import load_dotenv
from datetime import datetime, timedelta

CONSUMED_TICKET_KEY = "consumedTicket"

load_dotenv()
SLACK_TOKEN = os.getenv('SLACK_TOKEN')
SLACK_CHANNEL = os.getenv('SLACK_CHANNEL')
SLACK_LOG_CHANNEL = 'C08SZDPGSRX'

SLACK_WEBHOOK_URL = 'https://slack.com/api/chat.postMessage'

ISSUE_TICKET_PREFIX = 'INFO com.yourssu.signal.infrastructure.Notification - Issued ticket'
RETRY_ISSUE_TICKET_PREFIX = 'INFO com.yourssu.signal.infrastructure.Notification - RetryIssuedTicket'
CONSUME_TICKET_PREFIX = 'INFO com.yourssu.signal.infrastructure.Notification - Consumed ticket'

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
            print(f"디렉토리가 존재하지 않습니다: {directory}")
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


def create_analysis_message(hours, visitor_count, issued_ticket_count, consume_ticket_count) -> str:
    return f""" *💌 시그널 최근 {hours}시간 분석 보고서 💌*


    - *📅  분석 기간* : {(datetime.now() - timedelta(hours=hours)).strftime('%Y년 %m월 %d일 %H시 %M분')} ~ {datetime.now().strftime('%Y년 %m월 %d일 %H시 %M분')}
    - *👥  방문자 수* : {visitor_count} 명
    - *🎁  결제한 이용권* : {issued_ticket_count} 개
    - *💌  사용한 이용권* : {consume_ticket_count} 개
"""


def get_issued_ticket(line, dic):
    verification, uuid, ticket, available_ticket = line[line.find('&') + 1:].split(' ')
    dic[ISSUED_TICKET_KEY] += int(ticket)


def get_ticket_by_bank_deposit(line, dic):
    verification, uuid, ticket, available_ticket, name = line[line.find('&') + 1:].split(' ')
    dic[ISSUED_TICKET_KEY] += int(ticket)


def get_consumed_ticket_message(line, dic):
    dic[CONSUMED_TICKET_KEY] += 1


handler = {
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
    visit_count = create_count_visitor_message(hours)
    issued_ticket_count = dic[ISSUED_TICKET_KEY]
    consume_ticket_count = dic[CONSUMED_TICKET_KEY]
    message = create_analysis_message(hours, visit_count, issued_ticket_count, consume_ticket_count)
    send_slack_notification(message)
    print(message)

if __name__ == "__main__":
    hours = 1
    run(hours)
