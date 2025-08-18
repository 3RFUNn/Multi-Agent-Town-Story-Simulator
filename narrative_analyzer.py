# narrative_analyzer.py
# Analyzes agent diaries and daily stories for narrative cohesion and content overlap.
# Uses spaCy, TF-IDF, and matplotlib for NLP and visualization.

import os
import spacy
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import matplotlib.pyplot as plt
from matplotlib_venn import venn2

# --- spaCy Model Loading ---
# This will download the model if you don't have it, or load it if you do.
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    print("Downloading spaCy model 'en_core_web_sm'...")
    from spacy.cli import download
    download("en_core_web_sm")
    nlp = spacy.load("en_core_web_sm")

# --- Core Analysis Functions ---

def get_keywords_and_entities(text):
    """
    Extracts keywords (nouns, proper nouns, verbs) and named entities from a given text
    using the spaCy library.
    """
    doc = nlp(text)
    keywords = [token.lemma_ for token in doc if not token.is_stop and not token.is_punct and token.pos_ in ['NOUN', 'PROPN', 'VERB']]
    entities = [ent.text for ent in doc.ents]
    return set(keywords), set(entities)

def analyze_narratives(agent_logs, daily_story):
    """
    Performs a comprehensive analysis of the similarity and content overlap between
    a collection of agent logs and a single daily story.
    """
    # 1. Semantic Similarity using TF-IDF and Cosine Similarity
    # This measures how similar the documents are in terms of their word frequencies.
    vectorizer = TfidfVectorizer()
    # Combine all logs and the story into one list for vectorization
    all_texts = agent_logs + [daily_story]
    tfidf_matrix = vectorizer.fit_transform(all_texts)
    # Calculate the cosine similarity between the daily story (last row) and all agent logs
    cosine_sim = cosine_similarity(tfidf_matrix[-1], tfidf_matrix[:-1])
    # The result is an array of similarity scores, so we take the average
    avg_similarity = cosine_sim.mean()

    # 2. Keyword and Entity Overlap Analysis
    # This helps us understand if the key concepts and entities from the logs are in the story.
    story_keywords, story_entities = get_keywords_and_entities(daily_story)

    all_agent_keywords = set()
    all_agent_entities = set()

    for log in agent_logs:
        log_keywords, log_entities = get_keywords_and_entities(log)
        all_agent_keywords.update(log_keywords)
        all_agent_entities.update(log_entities)

    # Calculate the percentage of keywords and entities that overlap
    keyword_overlap = (len(story_keywords.intersection(all_agent_keywords)) / len(all_agent_keywords) * 100
                       if len(all_agent_keywords) > 0 else 0)
    entity_overlap = (len(story_entities.intersection(all_agent_entities)) / len(all_agent_entities) * 100
                      if len(all_agent_entities) > 0 else 0)

    return {
        "semantic_similarity": avg_similarity,
        "keyword_overlap_percentage": keyword_overlap,
        "entity_overlap_percentage": entity_overlap
    }

# --- Chart Generation Function ---

def generate_charts(results, agent_logs, daily_story):
    """
    Generates and displays charts to visualize the analysis results.
    """
    # 1. Bar Chart for the main similarity and overlap scores
    labels = ['Semantic Similarity', 'Keyword Overlap (%)', 'Entity Overlap (%)']
    # For the bar chart, we'll scale the semantic similarity to be on a 0-100 scale
    values = [
        results['semantic_similarity'] * 100,
        results['keyword_overlap_percentage'],
        results['entity_overlap_percentage']
    ]

    plt.figure(figsize=(10, 6))
    bars = plt.bar(labels, values, color=['#4A90E2', '#50E3C2', '#B8E986'])
    plt.ylabel('Score (out of 100)')
    plt.title('Narrative Cohesion Analysis')
    plt.ylim(0, 100)

    # Add the score labels on top of the bars
    for bar in bars:
        yval = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2.0, yval, f"{yval:.2f}", va='bottom', ha='center')

    plt.show()

    # 2. Venn Diagrams to show the overlap in keywords and entities
    story_keywords, story_entities = get_keywords_and_entities(daily_story)
    all_agent_keywords = set()
    all_agent_entities = set()

    for log in agent_logs:
        log_keywords, log_entities = get_keywords_and_entities(log)
        all_agent_keywords.update(log_keywords)
        all_agent_entities.update(log_entities)

    # Create a figure with two subplots
    plt.figure(figsize=(14, 7))

    # Keyword Venn Diagram
    plt.subplot(1, 2, 1)
    venn2(
        [all_agent_keywords, story_keywords],
        set_labels=('Agent Log Keywords', 'Daily Story Keywords'),
        set_colors=('#F5A623', '#4A90E2'),
        alpha=0.7
    )
    plt.title('Keyword Overlap')

    # Entity Venn Diagram
    plt.subplot(1, 2, 2)
    venn2(
        [all_agent_entities, story_entities],
        set_labels=('Agent Log Entities', 'Daily Story Entities'),
        set_colors=('#D0021B', '#50E3C2'),
        alpha=0.7
    )
    plt.title('Entity Overlap')

    plt.suptitle('Content Overlap between Agent Logs and Daily Story', fontsize=16)
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    plt.show()

def save_chart(data, labels, title, filename):
    import matplotlib.pyplot as plt
    plt.figure(figsize=(10, 6))
    bars = plt.bar(labels, data, color=['#4A90E2', '#50E3C2', '#B8E986'])
    plt.ylabel('Score (out of 100)')
    plt.title(title)
    plt.ylim(0, 100)
    for bar in bars:
        yval = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2.0, yval, f"{yval:.2f}", va='bottom', ha='center')
    plt.tight_layout()
    plt.savefig(filename)
    plt.close()

# --- Analysis for All Days ---

def analyze_all_days(base_dir):
    results_dir = 'results'
    os.makedirs(results_dir, exist_ok=True)
    day_dirs = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d)) and d.startswith('day_')]
    # Sort day_dirs numerically by extracting the number after 'day_'
    def day_key(day_name):
        try:
            return int(day_name.split('_')[1])
        except (IndexError, ValueError):
            return 0
    day_dirs = sorted(day_dirs, key=day_key)
    all_results = []
    weekday_results = {}
    # Collect results for each day
    for day in day_dirs:
        day_path = os.path.join(base_dir, day)
        files = sorted([f for f in os.listdir(day_path) if f.endswith('.txt')])
        if len(files) < 7:
            print(f"Skipping {day}: not enough files (found {len(files)})")
            continue
        agent_log_files = [os.path.join(day_path, f) for f in files[:6]]
        daily_story_file = os.path.join(day_path, files[-1])
        try:
            agent_logs_content = []
            for file_path in agent_log_files:
                with open(file_path, 'r', encoding='utf-8') as f:
                    agent_logs_content.append(f.read())
            with open(daily_story_file, 'r', encoding='utf-8') as f:
                daily_story_content = f.read()
            analysis_results = analyze_narratives(agent_logs_content, daily_story_content)
            story_filename = os.path.basename(daily_story_file)
            weekday = story_filename.split('_')[0] if '_' in story_filename else 'Unknown'
            all_results.append({
                'day': day,
                'weekday': weekday,
                'semantic_similarity': analysis_results['semantic_similarity'],
                'keyword_overlap_percentage': analysis_results['keyword_overlap_percentage'],
                'entity_overlap_percentage': analysis_results['entity_overlap_percentage']
            })
            if weekday not in weekday_results:
                weekday_results[weekday] = []
            weekday_results[weekday].append(all_results[-1])
        except FileNotFoundError as e:
            print(f"Error: Could not find a file in {day}. {e.filename}")
        except Exception as e:
            print(f"An unexpected error occurred in {day}: {e}")
    # Sort all_results numerically by day before writing outputs
    def result_day_key(result):
        try:
            return int(result['day'].split('_')[1])
        except (IndexError, ValueError):
            return 0
    all_results_sorted = sorted(all_results, key=result_day_key)
    # Write all days analysis to file
    with open(os.path.join(results_dir, 'all_days_analysis.txt'), 'w', encoding='utf-8') as f:
        f.write('Day\tWeekday\tSemanticSimilarity\tKeywordOverlap(%)\tEntityOverlap(%)\n')
        for result in all_results_sorted:
            f.write(f"{result['day']}\t{result['weekday']}\t{result['semantic_similarity']:.4f}\t{result['keyword_overlap_percentage']:.2f}\t{result['entity_overlap_percentage']:.2f}\n")
    # Write weekday comparisons
    for weekday, results in weekday_results.items():
        results_sorted = sorted(results, key=result_day_key)
        with open(os.path.join(results_dir, f"{weekday.lower()}_comparison.txt"), 'w', encoding='utf-8') as f:
            f.write('Day\tSemanticSimilarity\tKeywordOverlap(%)\tEntityOverlap(%)\n')
            for result in results_sorted:
                f.write(f"{result['day']}\t{result['semantic_similarity']:.4f}\t{result['keyword_overlap_percentage']:.2f}\t{result['entity_overlap_percentage']:.2f}\n")
    # Write full analysis summary
    with open(os.path.join(results_dir, 'full_analysis.txt'), 'w', encoding='utf-8') as f:
        f.write('--- All Days Analysis ---\n')
        for result in all_results_sorted:
            f.write(f"{result['day']} ({result['weekday']}): SemanticSimilarity={result['semantic_similarity']:.4f}, KeywordOverlap={result['keyword_overlap_percentage']:.2f}%, EntityOverlap={result['entity_overlap_percentage']:.2f}%\n")
        f.write('\n--- Weekday Comparisons ---\n')
        for weekday, results in weekday_results.items():
            results_sorted = sorted(results, key=result_day_key)
            f.write(f"\n{weekday}:\n")
            for result in results_sorted:
                f.write(f"  {result['day']}: SemanticSimilarity={result['semantic_similarity']:.4f}, KeywordOverlap={result['keyword_overlap_percentage']:.2f}%, EntityOverlap={result['entity_overlap_percentage']:.2f}%\n")
    # Save charts for each analysis type
    save_chart([r['semantic_similarity']*100 for r in all_results_sorted], [r['day'] for r in all_results_sorted], 'Semantic Similarity Across Days', os.path.join(results_dir, 'semantic_similarity_chart.png'))
    save_chart([r['keyword_overlap_percentage'] for r in all_results_sorted], [r['day'] for r in all_results_sorted], 'Keyword Overlap Across Days', os.path.join(results_dir, 'keyword_overlap_chart.png'))
    save_chart([r['entity_overlap_percentage'] for r in all_results_sorted], [r['day'] for r in all_results_sorted], 'Entity Overlap Across Days', os.path.join(results_dir, 'entity_overlap_chart.png'))

# --- Main Execution Block ---

if __name__ == "__main__":
    base_dir = os.path.join("simulation", "narrative", "daily_stories")
    analyze_all_days(base_dir)