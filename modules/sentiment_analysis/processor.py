from sqlalchemy import and_, exists
from modules.db.models import  MeetingTranscript, SessionLocal
from modules.sentiment_analysis.utils import process_meeting
from modules.sentiment_analysis.utils import get_sentiment_and_recommendations
from modules.sentiment_analysis.sentiment import * 
import sys
import nltk
nltk.download("punkt", quiet=True)
from nltk.tokenize import sent_tokenize as original_sent_tokenize

# Create our own tokenizer function that wraps the original
def safe_sent_tokenize(text):
    try:
        return original_sent_tokenize(text)
    except LookupError:
        # If punkt_tab is not found, use a simple regex-based splitter as fallback
        import re
        return re.split(r'(?<=[.!?])\s+', text)
from nltk.tokenize import sent_tokenize
# Replace the standard tokenizer with our safe version
sys.modules['nltk.tokenize'].sent_tokenize = safe_sent_tokenize




def process_new_meetings():
    '''
    Purpose:
        To automatically detect and process any new meetings or unprocessed transcripts.
        How it works:
        1. Finds all unprocessed meeting transcripts
        2. Groups them by meeting_id
        3. Processes each meeting's transcripts
        4. Stores all results in the database
    '''
    db = SessionLocal()
    try:
        # Find all unprocessed transcripts
        unprocessed_transcripts = db.query(MeetingTranscript).filter(
            MeetingTranscript.processed == False
        ).all()
        print(f"Found {len(unprocessed_transcripts)} unprocessed transcripts")
        
        if not unprocessed_transcripts:
            return {"message": "No unprocessed transcripts found"}

        # Group transcripts by meeting_id
        meetings_to_process = {}
        print('unprocessed transcript : ',unprocessed_transcripts)
        for transcript in unprocessed_transcripts:
            if transcript.meeting_id not in meetings_to_process:
                print("Transcript Meeting ID : ",transcript.meeting_id)
                print("Meeting to process -== ",meetings_to_process)
                meetings_to_process[transcript.meeting_id] = []
            meetings_to_process[transcript.meeting_id].append(transcript)

        print("Meeting processed :: ",meetings_to_process)

        results = []
        for meeting_id, transcripts in meetings_to_process.items():
            # Process each meeting
            meeting_results = process_meeting(meeting_id, db)
            results.extend(meeting_results)
        print("Results : ",results)
            
        db.commit()
        return {
            "message": f"Successfully processed {len(meetings_to_process)} meetings",
            "results": results
        }
    except Exception as e:
        db.rollback()
        print(f"Error processing meetings: {e}")
        return {"error": str(e)}
    finally:
        db.close()

