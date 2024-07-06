from pymongo.mongo_client import MongoClient,_MongoClientErrorHandler

client = MongoClient('mongodb://localhost:27017')

#initalize our workmatedb with db
db = client.workmate

collection_name = db["todo"]

#gets the collection of Users from workmate db in mongodb
user_collection = db["Users"]


document_details_collection = db["Knowledge_base"]

schema_info_collection = db['schema_info_gbq']

chat_history_by_session_collection = db['chat_history_by_session']
session_schema_collection = db['session_id_history']