#all models and schema used in this project will be defined here

from pydantic import BaseModel,Field

class BasicSubscription(BaseModel):
     status: bool
     duration : str

class UserSubscrpition(BaseModel):
      shopify_workmate: BasicSubscription
      knowledgebase_workmate:BasicSubscription

class User(BaseModel):
    name: str
    user_name: str
    user_email : str
    user_subscription: UserSubscrpition | None = None
    user_password : str


class Knowledge_base:
      user_id: str
      doc_file_name : str

class Chat_schema(BaseModel):
      session_id:str
      message:str
      sender:str
      sql_query:str

class Session_schema(BaseModel):
      session_id:str


      
