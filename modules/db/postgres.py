import os
import uuid
import logging
import psycopg2
from contextlib import contextmanager
from typing import List, Dict
from dotenv import load_dotenv

from models import Meeting, MeetingTranscript
from app01 import SessionLocal

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@contextmanager
def get_connection():
    try:
        conn = psycopg2.connect(
            dbname=os.getenv("POSTGRES_DB"),
            user=os.getenv("POSTGRES_USER"),
            password=os.getenv("POSTGRES_PASSWORD"),
            host=os.getenv("POSTGRES_HOST"),
            port=os.getenv("POSTGRES_PORT"),
        )
        yield conn
        conn.commit()
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise
    finally:
        if conn:
            conn.close()

# def insert_transcript(transcript: List[Dict], meeting_id: str = None):
#     """
#     Inserts transcript into the `meeting_transcripts` table.

#     Each entry must contain: speaker, role, start, end, transcription.
#     """
#     meeting_id = meeting_id or str(uuid.uuid4())

#     logger.info(f"Inserting transcript for meeting_id: {meeting_id}")

#     query = """
#     INSERT INTO meeting_transcript (meeting_id, name, text, processed)
#     VALUES (%s, %s, %s, %s)
#     """

#     with get_connection() as conn:
#         cursor = conn.cursor()
#         for entry in transcript:
#             try:
#                 cursor.execute(query, (
#                     meeting_id,
#                     entry.get("speaker"),
#                     entry.get("text"),
#                     False
#                 ))
#             except Exception as e:
#                 logger.error(f"Insert failed for entry {entry}: {e}")
#         cursor.close()

#     logger.info(f"Inserted {len(transcript)} rows for meeting {meeting_id}")
#     return meeting_id


from uuid import uuid4
from sqlalchemy.exc import SQLAlchemyError

def insert_transcript(transcript: List[Dict], meeting_id: str = None, title: str = None):
    session = SessionLocal()
    try:
        # Step 1: Create a new meeting
        meeting_id = meeting_id or str(uuid4())
        new_meeting = Meeting(id=meeting_id, title=title)
        session.add(new_meeting)

        # Step 2: Add all transcript entries linked to that meeting
        for entry in transcript:
            transcript_entry = MeetingTranscript(
                meeting_id=meeting_id,
                name=entry.get("speaker"),
                text=entry.get("text"),
                processed=False
            )
            session.add(transcript_entry)

        session.commit()
        logger.info(f"Inserted meeting and {len(transcript)} transcripts with meeting_id: {meeting_id}")
        return meeting_id

    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Error inserting transcript: {e}")
    finally:
        session.close()
