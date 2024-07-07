#This file deals with SQL chain and Google-bigquery integration

import os
import json
from dotenv import load_dotenv
from google.cloud import bigquery

#Langchain imports
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_core.messages import AIMessage,HumanMessage
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_groq import ChatGroq
from dbConfig.database import schema_info_collection
load_dotenv()
#os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = './gb-key.json'
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ['LANGCHAIN_API_KEY'] = os.getenv("LANGCHAIN_API_KEY")
groq_api_key = os.getenv("GROQC_API_KEY")

bq_key_json = os.getenv("BQ_KEY_JSON")

bq_key = json.loads(bq_key_json)
gbq_client = bigquery.Client.from_service_account_info(bq_key)


full_data_set_id ='bigquery-public-data.thelook_ecommerce'
schema_cache = None
#Code to get SCHEMA info from data set
def build_schema_desc(fields, prefix=""):
    """Build schema description, including nested fields."""
    desc = []
    for f in fields:
        d = f"{prefix}- Name: {f.name}, Type: {f.field_type}, Mode: {f.mode}"
        desc.append(d)
        if f.field_type == 'RECORD':
            sub_desc = build_schema_desc(f.fields, prefix + "    ")
            desc.extend(sub_desc)
    return desc

def fetch_schemas(dataset_id, client):
    """Fetch schema descriptions for all tables in a dataset."""
    schemas = []
    simple_table_list = []
    tables = client.list_tables(dataset_id)
    for table in tables:
        ref = client.get_table(table)
        simple_table_list.append(f"- {ref.project}.{ref.dataset_id}.{ref.table_id}")
        schema_desc = [f"Schema for {table.table_id}:"]
        schema_desc += build_schema_desc(ref.schema)
        schema_desc.append("")  # For newline
        schemas += schema_desc
    return "\n".join(simple_table_list) + "\n\n" + "\n".join(schemas)

def get_schema_info(_):
    # Check MongoDB cache
    schema_doc = schema_info_collection.find_one({"dataset_id": full_data_set_id})
    if schema_doc:
        return schema_doc['schema']
    else:
        # Fetch schema from BigQuery and save to MongoDB
        schema_info = fetch_schemas(full_data_set_id, gbq_client)
        schema_info_collection.insert_one({"dataset_id": full_data_set_id, "schema": schema_info})
        return schema_info

#Chain to generate SQL from NL
def sql_generator_chain():
   template = """Based on the table schema below, write a SQL query that would answer the user's question ,Take the conversation history into account:
                        {schema}
             Conversation History: {chat_history}
            Write only the SQL query and nothing else. Do not wrap the SQL query in any other text, not even backticks,dont use backticks inside the query as well and always add limit to not more than 10.
            for example:
            
            {{"Question": "Top 5 customer by total ammount spent?", "SQL_Query": "SELECT u.first_name, u.last_name, SUM(oi.sale_price) AS total_spent FROM bigquery-public-data.thelook_ecommerce.orders o JOIN bigquery-public-data.thelook_ecommerce.order_items oi ON o.order_id = oi.order_id JOIN bigquery-public-data.thelook_ecommerce.users u ON o.user_id = u.id GROUP BY u.id, u.first_name, u.last_name ORDER BY total_spent DESC LIMIT 5;"}} 
            {{"Question": "Which product categories and brands generate the highest profit margins make sure categories should be unique", "SQL_Query": "WITH profit_margins AS (SELECT p.category, p.brand, (p.retail_price - ii.cost) / p.retail_price AS profit_margin FROM bigquery-public-data.thelook_ecommerce.products p JOIN bigquery-public-data.thelook_ecommerce.inventory_items ii ON p.id = ii.product_id), category_brand_margins AS (SELECT category, brand, AVG(profit_margin) AS avg_profit_margin, ROW_NUMBER() OVER (PARTITION BY category ORDER BY AVG(profit_margin) DESC) AS rank FROM profit_margins GROUP BY category, brand) SELECT category, brand, avg_profit_margin FROM category_brand_margins WHERE rank = 1 ORDER BY avg_profit_margin DESC LIMIT 10;"}}
            {{"Question":"What is the average shipping time from order placement to delivery for each distribution center?","SQL_Query":"SELECT dc.name, AVG(TIMESTAMP_DIFF(oi.delivered_at, oi.created_at, HOUR)) AS avg_shipping_time FROM bigquery-public-data.thelook_ecommerce.order_items AS oi JOIN bigquery-public-data.thelook_ecommerce.orders AS o ON oi.order_id = o.order_id JOIN bigquery-public-data.thelook_ecommerce.inventory_items AS ii ON oi.inventory_item_id = ii.id JOIN bigquery-public-data.thelook_ecommerce.distribution_centers AS dc ON ii.product_distribution_center_id = dc.id WHERE oi.delivered_at IS NOT NULL GROUP BY dc.name;"}}
         \n{format_instructions}\n{question}\n
           """
   prompt = ChatPromptTemplate.from_template(template)

   class SQL_query(BaseModel):
         Question:str = Field(description="The user's actual question")
         SQL_Query : str = Field(description="The sql query the would answer the user's question")

   parser = JsonOutputParser(pydantic_object=SQL_query)
   prompt2 = PromptTemplate(
       template=template,
       input_variables=['schema','chat_history','question'],
       partial_variables={"format_instructions": parser.get_format_instructions()},
   )

   llm = ChatGroq(temperature=0, model_name="llama3-70b-8192",api_key=groq_api_key)

   return (
    RunnablePassthrough.assign(schema=get_schema_info)
    | prompt2
    | llm.bind(stop=["\nSQLResult:"])
    | parser
)

def parse(ai_message: AIMessage) -> str:
    """Parse the AI message to replace newlines with a blank space."""
    return ai_message.content.replace('\n', ' ')
def get_response(user_query: str,sql_query:str, chat_history: list):
    try:
       response = gbq_client.query(sql_query)
       response_text = response.to_dataframe().to_string(index=False)
    except Exception as e:
        # If there is an error, return the error message
        return {"error": str(e)}
    template = """
    You are a data analyst at a company. You are interacting with a user who is asking you questions about the company's database.
    Based on the table schema below, question, sql query, and sql response, write a natural language response.Your response should be in markdwon format , with proper highliting
    <SCHEMA>{schema}</SCHEMA>

    Conversation History: {chat_history}
    SQL Query: <SQL>{query}</SQL>
    User question: {question}
    SQL Response: {response}
    """
  
    prompt = ChatPromptTemplate.from_template(template)
  
  
  # llm = ChatOpenAI(model="gpt-4-0125-preview")
    llm = ChatGroq(temperature=0, model_name="llama3-70b-8192",api_key=groq_api_key)
  
  
    chain = (
    RunnablePassthrough.assign(
      schema=get_schema_info
    )
    | prompt
    | llm
    | StrOutputParser()
  )
  
    return chain.invoke({
    "question": user_query,
    "query":sql_query,
    "chat_history": chat_history,
    "response":response_text
  })


chat_history =[
     AIMessage(content="Hello! I'm a SQL assistant. Ask me anything about your database."),
]




# user_question = 'What are the total sales by distribution center?'
# chat_history.append(HumanMessage(content=user_question))

# # the_chain = get_sql_chain()
# sql_query_chain = sql_generator_chain()
# sql_query = sql_query_chain.invoke({
#     "question":user_question,
#     "chat_history":chat_history
# })
# print(sql_query)
# chat_history.append(AIMessage(content=sql_query))

# result = get_response(user_question,sql_query,chat_history)
# print(result)
# chat_history.append(AIMessage(content=result))

# user_question = 'Who has most order among them ?'
# chat_history.append(HumanMessage(content=user_question))
# # the_chain = get_sql_chain()
# sql_query_chain = sql_generator_chain()
# sql_query = sql_query_chain.invoke({
#     "question":user_question,
#     "chat_history":chat_history
# })
# chat_history.append(AIMessage(content=sql_query))

# result = get_response(user_question,sql_query,chat_history)

# print(result)

