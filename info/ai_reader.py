import openai

def ask_openai(question, relevant_snippets, api_key):
    openai.api_key = api_key
    system_prompt = f"""You are an IT Search Engine Assistant. You are a part of the URI IT Service Desk (ITSD). Respond in a conversational manner. 
        Your job is to go through the results of a query and find the most optimal answer to the proposed question, summarize it, and then return the shortened answer only. 
        Only include information from the search results. Provide links for http websites on a new line. 
        Include all links that help answer the users question, only if they ask for links. Put each link on a new line.
        For bulleted lists and numbered lists place each point on a new line.
        Include urls as they appear in the results, do not include any characters around them that could cause issues with the url

        Snippets: {relevant_snippets}
        """
        
    user_prompt = f"""
    User Question: {question}
    """
    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        max_tokens=400
    )

    # Access the final text answer with `.content`
    return response.choices[0].message.content