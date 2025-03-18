import os
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Function to set up the TfidfVectorizer and transform the sentences
def setup_tfidf(file_path):
    # Read file
    with open(file_path, 'r', encoding='utf-8') as f:
        file_content = f.read()

    # Split by comma, strip extra whitespace
    sentences = [s.strip() for s in file_content.split(',') if s.strip()]

    # Initialize TfidfVectorizer
    vectorizer = TfidfVectorizer()

    # Fit and transform the sentences
    sentence_vectors = vectorizer.fit_transform(sentences)
    
    return vectorizer, sentence_vectors, sentences

# Function to create indexes for all files in the data directory
def create_indexes(data_dir):
    indexes = {}
    for filename in os.listdir(data_dir):
        if filename.endswith('.json'):
            file_path = os.path.join(data_dir, filename)
            vectorizer, sentence_vectors, sentences = setup_tfidf(file_path)
            indexes[filename] = (vectorizer, sentence_vectors, sentences)
    return indexes

# Function to rank sentences based on cosine similarity
def rank_sentences(vectorizer, sentence_vectors, sentences, user_query, top_n):
    # Transform the query
    query_vector = vectorizer.transform([user_query])

    # Compute cosine similarity
    similarities = cosine_similarity(sentence_vectors, query_vector).flatten()

    # Pair each sentence with its similarity score and sort
    scored_sentences = list(zip(sentences, similarities))
    scored_sentences.sort(key=lambda x: x[1], reverse=True)

    # Get the top_n sentences
    top_results = scored_sentences[:top_n]
       
    return top_results

# Function to search for a query in the indexes
# This is called by other files to search for a query in the indexes
def search_in_indexes(indexes, query, top_n=10):
    results = {}

    # Collect top_n results from each file
    for filename, index_data in indexes.items():
        vectorizer, sentence_vectors, sentences = index_data
        top_results = rank_sentences(vectorizer, sentence_vectors, sentences, query, top_n)
        results[filename] = top_results

    # Combine all non-zero similarity results
    combined_results = []
    for filename, file_results in results.items():
        for sentence, score in file_results:
            if score > 0:
                combined_results.append((sentence, score))
    
    # Sort across all files by score, descending
    combined_results.sort(key=lambda x: x[1], reverse=True)

    # Take the top 20 overall
    top_overall = combined_results[:20] 

    # Return only the text from the top results
    only_text = [item[0] for item in top_overall]

    return only_text


    
    




