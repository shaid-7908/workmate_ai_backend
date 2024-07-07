from fastapi import APIRouter,UploadFile,Depends,HTTPException
from pydantic import BaseModel
from typing import Annotated
from Routes.Auth import oauth2_scheme
from dbConfig.database import document_details_collection 
from models.models_schema import Knowledge_base
from dotenv import load_dotenv
from Utils.user_login_and_verify import verify_token
from langchain_core.messages import AIMessage,HumanMessage
from Ai_chains.GBQ_sql_chain import sql_generator_chain,get_response
from dbConfig.database import chat_history_by_session_collection
from dbConfig.database import session_schema_collection
from models.models_schema import Chat_schema
from typing import List
import os
from dotenv import load_dotenv
import json
from google.cloud import bigquery
load_dotenv()

#so.environ['GOOGLE_APPLICATION_CREDENTIALS'] = './gb-key.json'
bq_key_json = os.getenv("BQ_KEY_JSON")

bq_key = json.loads(bq_key_json)
gbq_client = bigquery.Client.from_service_account_info(bq_key)

knowledgeBaseRouter = APIRouter(
    prefix="/sql_chain",
    tags=["Knowledge Base"],
    responses={404: {"description": "Not found"}},
)

class Item(BaseModel):
    question : str
    uuid : str

class SQLQUERY(BaseModel):
       sql_query:str

@knowledgeBaseRouter.post('/gbq_v1/askQuestion')
async def ask_question(Question:Item):
          token_data = True
          if token_data:
               chat_history =[
                           AIMessage(content="Hello! I'm a SQL assistant. Ask me anything about your database."),
                           ]
               chat_history.append(HumanMessage(content=Question.question))
               existing_session = session_schema_collection.find_one({"session_id":Question.uuid}) 
               if existing_session:
                    pass
               else:
                    session_schema_collection.insert_one({"session_id":Question.uuid})  
               sql_query_chain = sql_generator_chain()
               sql_query = sql_query_chain.invoke({
                     'question':Question.question,
                     'chat_history':chat_history
               })
               chat_history.append(AIMessage(content=sql_query['SQL_Query']))
               print(sql_query['SQL_Query'])
               Ai_response = get_response(Question.question,sql_query['SQL_Query'],chat_history)
               #chat_history.append(AIMessage(content=Ai_response))
               user_chat_data ={
                    'session_id':Question.uuid,
                    'message':Question.question,
                    'sender':'Human',
                    'sql_query':''
               }
               chat_history_by_session_collection.insert_one(user_chat_data)
               Ai_chat_data = {
                    'session_id':Question.uuid,
                    'message':Ai_response,
                    'sender':'Ai',
                    'sql_query':sql_query['SQL_Query']
               }
               chat_history_by_session_collection.insert_one(Ai_chat_data)
               return {'message':Ai_response,'sender':'Ai','sql_query':sql_query['SQL_Query']}


def get_column_type(field):
    if field.field_type in ['STRING', 'DATE', 'DATETIME', 'TIMESTAMP']:
        return 'categorical'
    elif field.field_type in ['INTEGER', 'FLOAT', 'NUMERIC', 'BIGNUMERIC']:
        return 'numerical'
    return 'other'

@knowledgeBaseRouter.post('/gbq_v1/sqlresult')
async def get_sql_result(SQL: SQLQUERY):
    try:
        query_job = gbq_client.query(SQL.sql_query)
        query_result = query_job.result()  # Wait for the job to complete.

        # Extracting the rows and column names from the query result
        rows = [dict(row) for row in query_result]
        column_fields = query_result.schema

        column_names = [field.name for field in column_fields]
        column_types = {field.name: get_column_type(field) for field in column_fields}

        # Generating valid column pairs
        valid_column_pairs = [
            {"x": x, "y": y}
            for x in column_names
            for y in column_names
            if column_types[x] == 'categorical' and column_types[y] == 'numerical'
        ]
        
        return {'results': rows, 'columns': column_names, 'valid_column_pairs': valid_column_pairs}
    except Exception as e:
        print(f"Error occurred: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    

@knowledgeBaseRouter.get("/chats/{session_id}", response_model=List[Chat_schema])
async def get_chats_by_session(session_id: str):
    chats = list(chat_history_by_session_collection.find({"session_id": session_id}))
    if not chats:
        raise HTTPException(status_code=404, detail="No chats found for this session ID")
    return [Chat_schema(**chat) for chat in chats]


class SessionWithFirstMessage(BaseModel):
    session_id: str
    first_message: str

@knowledgeBaseRouter.get("/chats/by_session_id",response_model=List[SessionWithFirstMessage])
async def get_sessions_with_first_message():
    try:
        # Fetch all session_ids from session_schema_collection
        sessions = session_schema_collection.find({}, {"_id": 0, "session_id": 1})
        
        result = []
        
        for session in sessions:
            session_id = session['session_id']
            # Fetch the first message for each session_id
            first_message_doc = chat_history_by_session_collection.find_one(
                {"session_id": session_id},
                {"_id": 0, "message": 1},
                sort=[("timestamp", 1)]  # Assuming you have a timestamp field to determine the first message
            )
            if first_message_doc:
                first_message = first_message_doc['message']
                result.append(SessionWithFirstMessage(session_id=session_id, first_message=first_message))
        
        return result
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))