from sqlalchemy import and_, exists
from models import Meeting, MeetingTranscript, SessionLocal
from utils import process_meeting
from utils import get_sentiment_and_recommendations
# from app import get_rolling_sentiment_from_transcript
from sentiment import * 




def get_rolling_sentiment_from_transcript(transcript: str, name: str):
    import nltk
    nltk.download("punkt", quiet=True)
    from nltk.tokenize import sent_tokenize

    sentences = sent_tokenize(transcript)
    result_data = []

    index = 1  # Sentence-wise index for the whole transcript
    for sentence in sentences:
        if sentence.lower().startswith(name.lower() + ":"):
            text = sentence.split(":", 1)[1].strip()  # Get text after "Name:"
            if text:
                # result = sentiment_pipeline(text)[0]
                # label = result["label"]
                # score = result["score"]

                # Convert to 0–100 sentiment score
                # sentiment_score = score * 100 if label == "POSITIVE" else (1 - score) * 100
                sentiment_score = get_sentiment(text)
                print("APP : ",sentiment_score)
                result_data.append({
                    "Index": index,
                    "Rolling Sentiment": round(sentiment_score, 2)
                })
        index += 1  # Increase index regardless of who said it

    return result_data

# def process_new_meetings():
#     '''
#         Purpose:
#             To automatically detect and process any new meetings that haven't been analyzed yet.

#             How it works:

#             Connects to the database.

#             Finds meetings that have no processed transcripts.

#             For each unprocessed meeting, it calls the process_meeting() function.

#             Returns the results (like sentiment, skills, tasks, etc.) after processing.
#     '''
#     db = SessionLocal()
#     try:
#         unprocessed = db.query(Meeting).filter(
#             ~exists().where(and_(
#                 MeetingTranscript.meeting_id == Meeting.id,
#                 MeetingTranscript.processed == True
#             ))
#         ).all()

#         results = []
#         for meeting in unprocessed:
#             results.extend(process_meeting(meeting.id, db))
#         return results
#     except Exception as e:
#         db.rollback()
#         print(f"Error processing meetings: {e}")
#         return []
#     finally:
#         db.close()



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
        
        if not unprocessed_transcripts:
            return {"message": "No unprocessed transcripts found"}

        # Group transcripts by meeting_id
        meetings_to_process = {}
        for transcript in unprocessed_transcripts:
            if transcript.meeting_id not in meetings_to_process:
                meetings_to_process[transcript.meeting_id] = []
            meetings_to_process[transcript.meeting_id].append(transcript)

        results = []
        for meeting_id, transcripts in meetings_to_process.items():
            # Process each meeting
            meeting_results = process_meeting(meeting_id, db)
            results.extend(meeting_results)
            
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

        
def process_transcript_and_store(meeting_id, name, role, transcript):
    session = SessionLocal()
    try:

        print(f"Transcript for name : {name} : {transcript} ")
        sentiment_score, skill, task, deadline, status = get_sentiment_and_recommendations(transcript, name)
        rolling_data = get_rolling_sentiment_from_transcript(transcript, name)
        sentiment__ = get_sentiment(transcript)
        return {
            "sentiment": sentiment__,
            "rolling": rolling_data,
            "task": task,
            "skill": skill,
            "deadline": deadline,
            "status": status
        }
    finally:
        session.close()
