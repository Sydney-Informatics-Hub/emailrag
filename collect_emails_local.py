import os
import re
import argparse
from datetime import datetime
from bs4 import BeautifulSoup
import lxml
import mailbox
import email
from pathlib import Path
import chardet
import pytz

def chunk_text(text, max_length=1000):
    # Normalize Unicode characters to the closest ASCII representation
    text = text.encode('ascii', 'ignore').decode('ascii')

    # Remove sequences of '>' used in email threads
    text = re.sub(r'\s*(?:>\s*){2,}', ' ', text)

    # Remove sequences of dashes, underscores, or non-breaking spaces
    text = re.sub(r'-{3,}', ' ', text)
    text = re.sub(r'_{3,}', ' ', text)
    text = re.sub(r'\s{2,}', ' ', text)  # Collapse multiple spaces into one

    # Replace URLs with a single space, or remove them
    text = re.sub(r'https?://\S+|www\.\S+', '', text)

    # Normalize whitespace to single spaces, strip leading/trailing whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    # Split text into sentences while preserving punctuation
    sentences = re.split(r'(?<=[.!?]) +', text)
    chunks = []
    current_chunk = ""
    
    for sentence in sentences:
        if len(current_chunk) + len(sentence) + 1 < max_length:
            current_chunk += (sentence + " ").strip()
        else:
            chunks.append(current_chunk)
            current_chunk = sentence + " "
    if current_chunk:
        chunks.append(current_chunk)

    return chunks

def save_chunks_to_vault(chunks):
    vault_path = "vault.txt"
    with open(vault_path, "a", encoding="utf-8") as vault_file:
        for chunk in chunks:
            vault_file.write(chunk.strip() + "\n")

def get_text_from_html(html_content):
    soup = BeautifulSoup(html_content, 'lxml')
    return soup.get_text()

def save_plain_text_content(email_content, email_id):
    text_content = ""
    if isinstance(email_content, str):
        # Assume it's already plain text
        text_content = email_content
    elif isinstance(email_content, bytes):
        # Assume it's HTML content
        text_content = get_text_from_html(email_content.decode('utf-8', errors='ignore'))

    chunks = chunk_text(text_content)
    save_chunks_to_vault(chunks)
    return text_content

def search_and_process_local_emails(mbox_file_path, keyword=None, start_date=None, end_date=None):

    try:
        # Open the mbox file
        mbox = mailbox.mbox(mbox_file_path)
    except FileNotFoundError:
        print(f"Error: The file {mbox_file_path} was not found.")
        return
    except PermissionError:
        print(f"Error: Permission denied to access {mbox_file_path}.")
        return
    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")
        return
    
    # Iterate through messages
    emails = []
    for key, message in mbox.items():
        # Extract subject
        subject = message['subject']
        if subject:
            # Decode subject
            decoded_subject = email.header.decode_header(subject)[0][0]
            if isinstance(decoded_subject, bytes):
                payload = decoded_subject
                detected_encoding = chardet.detect(payload)['encoding']
                try:
                    subject = payload.decode(detected_encoding)
                except (UnicodeDecodeError, TypeError):
                    subject = payload.decode('utf-8', errors='ignore')
            else:
                subject = decoded_subject

        # Extract date
        date_str = message['date']
        if date_str:
            date = email.utils.parsedate_to_datetime(date_str)
        else:
            continue  # Skip messages without a date

        content = ''
        if message.is_multipart():
            for part in message.walk():
                if part.get_content_type() == "text/plain":
                    payload = part.get_payload(decode=True)
                    # Detect encoding
                    if payload:
                        detected_encoding = chardet.detect(payload)['encoding']
                        try:
                            content += payload.decode(detected_encoding)
                        except (UnicodeDecodeError, TypeError):
                            content += payload.decode('utf-8', errors='ignore')
        else:
            payload = message.get_payload(decode=True)
            if payload:
                detected_encoding = chardet.detect(payload)['encoding']
                try:
                    content = payload.decode(detected_encoding)
                except (UnicodeDecodeError, TypeError):
                    content = payload.decode('utf-8', errors='ignore')

        # Check if the email matches the search criteria
        #if keyword:
        #    if keyword.lower() in subject.lower() or keyword.lower() in content.lower():
        
        # print(start_date,date,end_date)
        if (not start_date or date >= start_date) and (not end_date or date <= end_date):
        #            print(f"Matching email found - ID: {key}")

            emails.append([content.lower(), date, subject.lower()])

    for emess in emails:
        print(f"Subject: {emess[2]}, Date: {emess[1]}")
        save_plain_text_content(emess[0], 0)


def main():
    parser = argparse.ArgumentParser(description="Search and process emails from local Mac Mail client.")
    parser.add_argument("--mboxfile", help="The mbox file to process (In Mail.app, right click on Folder > Export Mailbox..).", default="./mbox")
    parser.add_argument("--keyword", help="The keyword to search for in the email bodies.", default="")
    parser.add_argument("--startdate", help="Start date in DD.MM.YYYY format.", required=False)
    parser.add_argument("--enddate", help="End date in DD.MM.YYYY format.", required=False)
    args = parser.parse_args()
    #python collect_emails_local.py --mboxfile /Users/nbut3013/Documents/MAILDATA/SentItems.mbox/mbox --startdate 01.01.2024 --enddate 31.12.2024

    start_date = None
    end_date = None

    if args.startdate and args.enddate:
        try:
            start_date = datetime.strptime(args.startdate, "%d.%m.%Y")
            end_date = datetime.strptime(args.enddate, "%d.%m.%Y")
            tz=pytz.UTC
            start_date = tz.localize(start_date)
            end_date = tz.localize(end_date)
        except ValueError as e:
            print(f"Error: Date format is incorrect. Please use DD.MM.YYYY format. Details: {e}")
            return
    elif args.startdate or args.enddate:
        print("Both start date and end date must be provided together.")
        return

    search_and_process_local_emails(args.mboxfile, keyword=args.keyword, start_date=start_date, end_date=end_date)

if __name__ == "__main__":
    main()