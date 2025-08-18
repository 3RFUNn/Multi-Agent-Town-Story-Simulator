#!/usr/bin/env python3
"""
Narrative Analyzer for Agent Town Simulation
============================================

This module provides comprehensive analysis of generated narratives from the simulation, 
evaluating multiple aspects of narrative quality and agent behavior patterns.

Features:
- Diary-story similarity analysis using TF-IDF and cosine similarity
- Day-of-week consistency tracking across simulation periods  
- Sentiment analysis and behavioral pattern detection
- Routine change tracking over time
- Agent interaction network visualization
- Comprehensive reporting with statistical summaries

Usage:
    python narrative_analyzer.py

Output:
    All results are saved to the 'results' directory with CSV files, 
    visualizations, and a comprehensive text report.

Requirements:
    pandas, matplotlib, seaborn, scikit-learn, textblob, networkx, numpy

Author: Agent Town Simulation Team
Date: August 2025
"""

import os
import sys
import json
import warnings
from typing import Dict, List, Tuple, Optional, Any
from collections import defaultdict, Counter
from dataclasses import dataclass

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import networkx as nx
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Suppress warnings for cleaner output
warnings.filterwarnings('ignore')


def setup_dependencies() -> bool:
    """
    Set up required dependencies including NLTK data for TextBlob.
    
    Returns:
        bool: True if TextBlob is available and properly configured
    """
    try:
        import nltk
        print("Setting up NLTK dependencies...")
        
        # Required NLTK data packages
        nltk_packages = ['punkt_tab', 'vader_lexicon', 'brown', 'punkt', 'stopwords']
        
        for package in nltk_packages:
            try:
                nltk.download(package, quiet=True)
            except Exception as e:
                print(f"Warning: Could not download {package}: {e}")
        
        # Import TextBlob after NLTK setup
        from textblob import TextBlob
        
        # Test TextBlob functionality
        test_blob = TextBlob("This is a test sentence.")
        _ = test_blob.sentiment.polarity
        
        print("TextBlob dependencies configured successfully.")
        return True
        
    except ImportError:
        print("Warning: TextBlob not available. Sentiment analysis will use fallback methods.")
        return False
    except Exception as e:
        print(f"Warning: TextBlob configuration failed: {e}")
        return False


@dataclass
class AnalysisConfig:
    """Configuration settings for the narrative analyzer."""
    
    stories_dir: str = "simulation/narrative/daily_stories"
    results_dir: str = "results"
    agents: List[str] = None
    day_names: List[str] = None
    
    def __post_init__(self):
        if self.agents is None:
            self.agents = ['alex', 'bella', 'charlie', 'diana', 'ethan', 'fiona']
        if self.day_names is None:
            self.day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 
                            'Friday', 'Saturday', 'Sunday']


@dataclass
class BehaviorKeywords:
    """Predefined keyword sets for behavioral analysis."""
    
    positive_emotions: List[str] = None
    negative_emotions: List[str] = None
    social_behavior: List[str] = None
    work_behavior: List[str] = None
    routine_words: List[str] = None
    activity_keywords: List[str] = None
    
    def __post_init__(self):
        if self.positive_emotions is None:
            self.positive_emotions = [
                'happy', 'excited', 'great', 'good', 'love', 'enjoy', 
                'fun', 'amazing', 'wonderful', 'pleased', 'delighted'
            ]
        if self.negative_emotions is None:
            self.negative_emotions = [
                'sad', 'frustrated', 'annoyed', 'tired', 'stressed', 
                'disappointed', 'worried', 'upset', 'angry', 'anxious'
            ]
        if self.social_behavior is None:
            self.social_behavior = [
                'chat', 'talk', 'conversation', 'friends', 'social', 'meet', 
                'hang out', 'party', 'gathering', 'visit'
            ]
        if self.work_behavior is None:
            self.work_behavior = [
                'work', 'office', 'productive', 'tasks', 'busy', 'focus', 
                'professional', 'meeting', 'deadline', 'project'
            ]
        if self.routine_words is None:
            self.routine_words = [
                'usual', 'routine', 'schedule', 'regular', 'always', 
                'typically', 'normally', 'daily', 'habit'
            ]
        if self.activity_keywords is None:
            self.activity_keywords = [
                'wake up', 'breakfast', 'coffee', 'work', 'lunch', 'dinner', 
                'gym', 'exercise', 'classes', 'study', 'home', 'sleep', 
                'park', 'cafe', 'office', 'campus', 'shopping', 'cooking'
            ]


class NarrativeAnalyzer:
    """
    Comprehensive narrative analysis system for agent town simulation.
    
    This class provides tools to analyze the quality and patterns in generated
    narratives, including similarity analysis, sentiment tracking, routine analysis,
    and agent interaction networks.
    
    Attributes:
        config (AnalysisConfig): Configuration settings
        keywords (BehaviorKeywords): Keyword sets for behavioral analysis
        textblob_available (bool): Whether TextBlob is available for sentiment analysis
        agent_texts (Dict): Loaded agent diary texts by day
        daily_stories (Dict): Loaded daily story texts by day
    """
    
    def __init__(self, config: Optional[AnalysisConfig] = None):
        """
        Initialize the narrative analyzer.
        
        Args:
            config: Optional configuration object. Uses defaults if not provided.
        """
        self.config = config or AnalysisConfig()
        self.keywords = BehaviorKeywords()
        self.textblob_available = setup_dependencies()
        
        # Create results directory
        os.makedirs(self.config.results_dir, exist_ok=True)
        
        # Data storage
        self.agent_texts: Dict[str, Dict[str, str]] = {}
        self.daily_stories: Dict[str, str] = {}
        
        # Set up matplotlib styling
        plt.style.use('seaborn-v0_8')
        sns.set_palette("husl")
        
        print(f"Narrative Analyzer initialized:")
        print(f"  Stories directory: {self.config.stories_dir}")
        print(f"  Results directory: {self.config.results_dir}")
        print(f"  TextBlob available: {self.textblob_available}")
    
    def discover_available_days(self) -> List[int]:
        """
        Discover all available simulation days in the stories directory.
        
        Returns:
            List[int]: Sorted list of available day numbers
            
        Raises:
            FileNotFoundError: If stories directory doesn't exist
        """
        if not os.path.exists(self.config.stories_dir):
            raise FileNotFoundError(f"Stories directory not found: {self.config.stories_dir}")
        
        days = []
        for item in os.listdir(self.config.stories_dir):
            item_path = os.path.join(self.config.stories_dir, item)
            if os.path.isdir(item_path) and item.startswith('day_'):
                try:
                    day_num = int(item.split('_')[1])
                    days.append(day_num)
                except (ValueError, IndexError):
                    print(f"Warning: Invalid day directory format: {item}")
                    continue
        
        return sorted(days)
    
    def load_simulation_data(self) -> None:
        """
        Load all agent diaries and daily stories from the simulation.
        
        This method reads all available text files and organizes them by day
        and agent for analysis.
        """
        print("Loading simulation narrative data...")
        available_days = self.discover_available_days()
        
        if not available_days:
            raise ValueError("No simulation days found in stories directory")
        
        loaded_days = 0
        for day_num in available_days:
            day_dir = os.path.join(self.config.stories_dir, f"day_{day_num}")
            
            # Determine day of week (cycling through week)
            day_of_week = self.config.day_names[(day_num - 1) % 7]
            day_key = f"day_{day_num}_{day_of_week}"
            
            self.agent_texts[day_key] = {}
            
            # Load agent diaries
            agents_loaded = 0
            for agent in self.config.agents:
                agent_file = os.path.join(day_dir, f"{agent}_{day_of_week}.txt")
                if os.path.exists(agent_file):
                    try:
                        with open(agent_file, 'r', encoding='utf-8') as f:
                            self.agent_texts[day_key][agent] = f.read().strip()
                            agents_loaded += 1
                    except Exception as e:
                        print(f"Warning: Could not load {agent_file}: {e}")
            
            # Load daily story
            story_file = os.path.join(day_dir, f"{day_of_week}_story.txt")
            if os.path.exists(story_file):
                try:
                    with open(story_file, 'r', encoding='utf-8') as f:
                        self.daily_stories[day_key] = f.read().strip()
                except Exception as e:
                    print(f"Warning: Could not load {story_file}: {e}")
            
            if agents_loaded > 0:
                loaded_days += 1
        
        print(f"Successfully loaded data for {loaded_days} days: {available_days}")
        print(f"Total agent entries: {sum(len(agents) for agents in self.agent_texts.values())}")
        print(f"Total daily stories: {len(self.daily_stories)}")
    
    def analyze_diary_story_similarity(self) -> pd.DataFrame:
        """
        Analyze semantic similarity between agent diaries and daily stories.
        
        Uses TF-IDF vectorization and cosine similarity to measure how well
        each agent's diary content is represented in the compiled daily story.
        
        Returns:
            pd.DataFrame: Similarity scores with columns: day, agent, similarity, day_of_week
        """
        print("Analyzing diary-story similarity...")
        similarity_results = []
        
        for day_key, agent_texts in self.agent_texts.items():
            if day_key not in self.daily_stories:
                print(f"Warning: No daily story found for {day_key}")
                continue
            
            daily_story = self.daily_stories[day_key]
            if not daily_story.strip():
                print(f"Warning: Empty daily story for {day_key}")
                continue
            
            # Prepare texts for vectorization
            valid_agents = []
            agent_contents = []
            
            for agent in self.config.agents:
                if agent in agent_texts and agent_texts[agent].strip():
                    valid_agents.append(agent)
                    agent_contents.append(agent_texts[agent])
            
            if len(valid_agents) < 2:  # Need at least 2 texts for meaningful analysis
                print(f"Warning: Insufficient agent data for {day_key}")
                continue
            
            try:
                # Create TF-IDF vectors for all texts
                all_texts = agent_contents + [daily_story]
                vectorizer = TfidfVectorizer(
                    max_features=1000, 
                    stop_words='english', 
                    ngram_range=(1, 2),
                    min_df=1,
                    max_df=0.9
                )
                tfidf_matrix = vectorizer.fit_transform(all_texts)
                
                # Calculate similarity of each agent diary to daily story
                story_vector = tfidf_matrix[-1]
                
                for i, agent in enumerate(valid_agents):
                    agent_vector = tfidf_matrix[i]
                    similarity = cosine_similarity(agent_vector, story_vector)[0][0]
                    
                    similarity_results.append({
                        'day': day_key,
                        'agent': agent,
                        'similarity': similarity,
                        'day_of_week': day_key.split('_')[-1]
                    })
                    
            except Exception as e:
                print(f"Warning: Similarity analysis failed for {day_key}: {e}")
                continue
        
        if not similarity_results:
            raise ValueError("No similarity data could be computed")
        
        # Convert to DataFrame and save
        df = pd.DataFrame(similarity_results)
        df.to_csv(os.path.join(self.config.results_dir, 'diary_story_similarity.csv'), index=False)
        
        # Create visualization
        self._create_similarity_heatmap(df)
        
        # Generate summary statistics
        self._create_similarity_summary(df)
        
        return df
    
    def _create_similarity_heatmap(self, df: pd.DataFrame) -> None:
        """Create and save similarity heatmap visualization."""
        plt.figure(figsize=(15, 8))
        
        # Pivot data for heatmap
        pivot_data = df.pivot(index='day', columns='agent', values='similarity')
        
        # Create heatmap
        sns.heatmap(
            pivot_data, 
            annot=True, 
            cmap='viridis', 
            fmt='.3f',
            cbar_kws={'label': 'Cosine Similarity Score'}
        )
        
        plt.title('Agent Diary to Daily Story Similarity Scores', fontsize=16, fontweight='bold')
        plt.xlabel('Agent', fontsize=12)
        plt.ylabel('Simulation Day', fontsize=12)
        plt.xticks(rotation=45)
        plt.yticks(rotation=0)
        plt.tight_layout()
        
        # Save plot
        plt.savefig(
            os.path.join(self.config.results_dir, 'diary_story_similarity_heatmap.png'), 
            dpi=300, 
            bbox_inches='tight'
        )
        plt.close()
    
    def _create_similarity_summary(self, df: pd.DataFrame) -> None:
        """Generate and save similarity summary statistics."""
        summary = df.groupby('agent')['similarity'].agg([
            'count', 'mean', 'std', 'min', 'max'
        ]).round(3)
        summary.columns = ['Entries', 'Mean', 'Std Dev', 'Min', 'Max']
        summary.to_csv(os.path.join(self.config.results_dir, 'similarity_summary_stats.csv'))
    
    def analyze_day_consistency(self) -> Tuple[List[Dict], List[Dict]]:
        """
        Analyze consistency of narratives across same days of the week.
        
        Compares how similar agent behaviors and daily stories are on the same
        day of the week across different simulation weeks.
        
        Returns:
            Tuple[List[Dict], List[Dict]]: Agent consistency results, story consistency results
        """
        print("Analyzing day-of-week consistency...")
        
        # Group days by day of week
        day_groups = defaultdict(list)
        for day_key in self.agent_texts.keys():
            day_of_week = day_key.split('_')[-1]
            day_groups[day_of_week].append(day_key)
        
        # Analyze agent consistency across same days
        agent_consistency = self._analyze_agent_consistency(day_groups)
        
        # Analyze story consistency across same days
        story_consistency = self._analyze_story_consistency(day_groups)
        
        return agent_consistency, story_consistency
    
    def _analyze_agent_consistency(self, day_groups: Dict) -> List[Dict]:
        """Analyze agent behavioral consistency across same days of week."""
        consistency_results = []
        
        for day_of_week, days in day_groups.items():
            if len(days) < 2:
                continue
            
            for agent in self.config.agents:
                agent_texts = []
                valid_days = []
                
                # Collect all texts for this agent on this day of week
                for day_key in days:
                    if agent in self.agent_texts[day_key]:
                        text = self.agent_texts[day_key][agent].strip()
                        if text:
                            agent_texts.append(text)
                            valid_days.append(day_key)
                
                if len(agent_texts) < 2:
                    continue
                
                try:
                    # Calculate pairwise similarities
                    vectorizer = TfidfVectorizer(
                        max_features=500, 
                        stop_words='english',
                        min_df=1
                    )
                    tfidf_matrix = vectorizer.fit_transform(agent_texts)
                    similarity_matrix = cosine_similarity(tfidf_matrix)
                    
                    # Calculate average similarity (excluding diagonal)
                    n = len(agent_texts)
                    if n > 1:
                        avg_similarity = (similarity_matrix.sum() - n) / (n * (n - 1))
                        
                        consistency_results.append({
                            'day_of_week': day_of_week,
                            'agent': agent,
                            'avg_similarity': avg_similarity,
                            'num_instances': len(agent_texts)
                        })
                        
                except Exception as e:
                    print(f"Warning: Consistency analysis failed for {agent} on {day_of_week}: {e}")
                    continue
        
        # Save results and create visualization
        if consistency_results:
            df_agents = pd.DataFrame(consistency_results)
            df_agents.to_csv(os.path.join(self.config.results_dir, 'agent_day_consistency.csv'), index=False)
            self._create_consistency_heatmap(df_agents)
        
        return consistency_results
    
    def _analyze_story_consistency(self, day_groups: Dict) -> List[Dict]:
        """Analyze daily story consistency across same days of week."""
        story_consistency = []
        
        for day_of_week, days in day_groups.items():
            if len(days) < 2:
                continue
            
            stories = []
            for day_key in days:
                if day_key in self.daily_stories:
                    story = self.daily_stories[day_key].strip()
                    if story:
                        stories.append(story)
            
            if len(stories) < 2:
                continue
            
            try:
                vectorizer = TfidfVectorizer(max_features=500, stop_words='english', min_df=1)
                tfidf_matrix = vectorizer.fit_transform(stories)
                similarity_matrix = cosine_similarity(tfidf_matrix)
                
                n = len(stories)
                avg_similarity = (similarity_matrix.sum() - n) / (n * (n - 1))
                
                story_consistency.append({
                    'day_of_week': day_of_week,
                    'avg_similarity': avg_similarity,
                    'num_instances': len(stories)
                })
                
            except Exception as e:
                print(f"Warning: Story consistency analysis failed for {day_of_week}: {e}")
                continue
        
        # Save results
        if story_consistency:
            df_stories = pd.DataFrame(story_consistency)
            df_stories.to_csv(os.path.join(self.config.results_dir, 'story_day_consistency.csv'), index=False)
        
        return story_consistency
    
    def _create_consistency_heatmap(self, df: pd.DataFrame) -> None:
        """Create and save consistency analysis heatmap."""
        plt.figure(figsize=(12, 6))
        
        pivot_data = df.pivot(index='day_of_week', columns='agent', values='avg_similarity')
        
        sns.heatmap(
            pivot_data, 
            annot=True, 
            cmap='coolwarm', 
            fmt='.3f',
            cbar_kws={'label': 'Average Similarity Score'}
        )
        
        plt.title('Agent Consistency Across Same Days of Week', fontsize=16, fontweight='bold')
        plt.xlabel('Agent', fontsize=12)
        plt.ylabel('Day of Week', fontsize=12)
        plt.tight_layout()
        
        plt.savefig(
            os.path.join(self.config.results_dir, 'agent_consistency_heatmap.png'), 
            dpi=300, 
            bbox_inches='tight'
        )
        plt.close()
    
    def analyze_sentiment_and_behavior(self) -> pd.DataFrame:
        """
        Analyze agent sentiment patterns and behavioral indicators.
        
        Performs sentiment analysis using TextBlob (if available) and tracks
        behavioral keywords to understand agent personality and mood patterns.
        
        Returns:
            pd.DataFrame: Sentiment and behavior analysis results
        """
        print("Analyzing sentiment and behavioral patterns...")
        sentiment_results = []
        
        # Import TextBlob if available
        TextBlob = None
        if self.textblob_available:
            try:
                from textblob import TextBlob
            except ImportError:
                print("Warning: TextBlob import failed, using fallback methods")
        
        for day_key, agent_texts in self.agent_texts.items():
            for agent in self.config.agents:
                if agent not in agent_texts:
                    continue
                
                text = agent_texts[agent]
                if not text.strip():
                    continue
                
                # Sentiment analysis with error handling
                sentiment_polarity, sentiment_subjectivity, sentence_count = self._analyze_text_sentiment(
                    text, TextBlob
                )
                
                # Behavioral keyword analysis
                behavior_scores = self._analyze_behavioral_keywords(text)
                
                # Text statistics
                word_count = len(text.split())
                avg_sentence_length = word_count / max(sentence_count, 1)
                
                sentiment_results.append({
                    'day': day_key,
                    'agent': agent,
                    'day_of_week': day_key.split('_')[-1],
                    'sentiment_polarity': sentiment_polarity,
                    'sentiment_subjectivity': sentiment_subjectivity,
                    'word_count': word_count,
                    'sentence_count': sentence_count,
                    'avg_sentence_length': avg_sentence_length,
                    **behavior_scores
                })
        
        if not sentiment_results:
            raise ValueError("No sentiment data could be computed")
        
        # Convert to DataFrame and save
        df = pd.DataFrame(sentiment_results)
        df.to_csv(os.path.join(self.config.results_dir, 'sentiment_behavior_analysis.csv'), index=False)
        
        # Create visualizations
        self._create_sentiment_visualizations(df)
        
        return df
    
    def _analyze_text_sentiment(self, text: str, TextBlob) -> Tuple[float, float, int]:
        """Analyze sentiment of text using TextBlob or fallback methods."""
        sentiment_polarity = 0.0
        sentiment_subjectivity = 0.0
        sentence_count = 1
        
        if TextBlob and self.textblob_available:
            try:
                blob = TextBlob(text)
                sentiment_polarity = blob.sentiment.polarity
                sentiment_subjectivity = blob.sentiment.subjectivity
                sentence_count = len(blob.sentences) if blob.sentences else 1
            except Exception as e:
                print(f"Warning: TextBlob sentiment analysis failed: {e}")
                sentence_count = len([s for s in text.split('.') if s.strip()]) or 1
        else:
            # Fallback: simple sentence counting
            sentence_count = len([s for s in text.split('.') if s.strip()]) or 1
        
        return sentiment_polarity, sentiment_subjectivity, sentence_count
    
    def _analyze_behavioral_keywords(self, text: str) -> Dict[str, int]:
        """Analyze behavioral keywords in text."""
        text_lower = text.lower()
        behavior_scores = {}
        
        keyword_categories = {
            'positive_emotions': self.keywords.positive_emotions,
            'negative_emotions': self.keywords.negative_emotions,
            'social_behavior': self.keywords.social_behavior,
            'work_behavior': self.keywords.work_behavior,
            'routine_words': self.keywords.routine_words
        }
        
        for category, keywords in keyword_categories.items():
            count = sum(text_lower.count(keyword) for keyword in keywords)
            behavior_scores[category] = count
        
        return behavior_scores
    
    def _create_sentiment_visualizations(self, df: pd.DataFrame) -> None:
        """Create and save sentiment analysis visualizations."""
        plt.figure(figsize=(15, 10))
        
        # Average sentiment by agent
        plt.subplot(2, 2, 1)
        agent_sentiment = df.groupby('agent')['sentiment_polarity'].mean().sort_values()
        colors = ['red' if x < 0 else 'green' if x > 0.1 else 'gray' for x in agent_sentiment.values]
        agent_sentiment.plot(kind='bar', color=colors)
        plt.title('Average Sentiment by Agent', fontsize=12, fontweight='bold')
        plt.ylabel('Sentiment Polarity')
        plt.xticks(rotation=45)
        plt.axhline(y=0, color='black', linestyle='--', alpha=0.3)
        
        # Average sentiment by day of week
        plt.subplot(2, 2, 2)
        day_sentiment = df.groupby('day_of_week')['sentiment_polarity'].mean()
        day_sentiment.plot(kind='bar', color='lightcoral')
        plt.title('Average Sentiment by Day of Week', fontsize=12, fontweight='bold')
        plt.ylabel('Sentiment Polarity')
        plt.xticks(rotation=45)
        plt.axhline(y=0, color='black', linestyle='--', alpha=0.3)
        
        # Positive vs negative emotions scatter plot
        plt.subplot(2, 2, 3)
        sns.scatterplot(data=df, x='positive_emotions', y='negative_emotions', hue='agent', alpha=0.7)
        plt.title('Positive vs Negative Emotions by Agent', fontsize=12, fontweight='bold')
        plt.xlabel('Positive Emotion Keywords')
        plt.ylabel('Negative Emotion Keywords')
        
        # Social vs work behavior scatter plot
        plt.subplot(2, 2, 4)
        sns.scatterplot(data=df, x='social_behavior', y='work_behavior', hue='agent', alpha=0.7)
        plt.title('Social vs Work Behavior by Agent', fontsize=12, fontweight='bold')
        plt.xlabel('Social Behavior Keywords')
        plt.ylabel('Work Behavior Keywords')
        
        plt.tight_layout()
        plt.savefig(
            os.path.join(self.config.results_dir, 'sentiment_behavior_plots.png'), 
            dpi=300, 
            bbox_inches='tight'
        )
        plt.close()
    
    def analyze_routine_patterns(self) -> pd.DataFrame:
        """
        Track routine patterns and changes over time.
        
        Monitors mentions of daily activities and routines to understand
        how agent behaviors evolve throughout the simulation.
        
        Returns:
            pd.DataFrame: Routine analysis results
        """
        print("Analyzing routine patterns and changes...")
        
        routine_patterns = defaultdict(lambda: defaultdict(dict))
        routine_data = []
        
        for day_key, agent_texts in self.agent_texts.items():
            day_num = int(day_key.split('_')[1])
            
            for agent in self.config.agents:
                if agent not in agent_texts:
                    continue
                
                text = agent_texts[agent].lower()
                
                # Count activity mentions
                for activity in self.keywords.activity_keywords:
                    count = text.count(activity.lower())
                    routine_patterns[agent][day_num][activity] = count
                    
                    routine_data.append({
                        'agent': agent,
                        'day': day_num,
                        'activity': activity,
                        'mentions': count
                    })
        
        if not routine_data:
            raise ValueError("No routine data could be computed")
        
        # Convert to DataFrame and save
        df = pd.DataFrame(routine_data)
        df.to_csv(os.path.join(self.config.results_dir, 'routine_analysis.csv'), index=False)
        
        # Create visualizations
        self._create_routine_visualizations(df)
        
        return df
    
    def _create_routine_visualizations(self, df: pd.DataFrame) -> None:
        """Create and save routine pattern visualizations."""
        plt.figure(figsize=(20, 12))
        
        # Top activities by agent
        top_activities = df.groupby(['agent', 'activity'])['mentions'].sum().reset_index()
        top_activities = top_activities.sort_values('mentions', ascending=False)
        
        for i, agent in enumerate(self.config.agents):
            plt.subplot(2, 3, i + 1)
            agent_data = top_activities[top_activities['agent'] == agent].head(8)
            
            if not agent_data.empty:
                colors = plt.cm.Set3(np.linspace(0, 1, len(agent_data)))
                bars = plt.bar(range(len(agent_data)), agent_data['mentions'], color=colors)
                plt.title(f'{agent.title()} - Top Activities', fontsize=12, fontweight='bold')
                plt.xticks(
                    range(len(agent_data)), 
                    agent_data['activity'], 
                    rotation=45, 
                    ha='right'
                )
                plt.ylabel('Total Mentions')
                
                # Add value labels on bars
                for bar, value in zip(bars, agent_data['mentions']):
                    if value > 0:
                        plt.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1, 
                               str(value), ha='center', va='bottom', fontsize=8)
        
        plt.tight_layout()
        plt.savefig(
            os.path.join(self.config.results_dir, 'routine_patterns.png'), 
            dpi=300, 
            bbox_inches='tight'
        )
        plt.close()
    
    def analyze_agent_connections(self) -> Tuple[pd.DataFrame, List[Dict]]:
        """
        Analyze connections and interactions between agents.
        
        Creates interaction networks based on how often agents mention
        each other in their diaries, indicating social connections.
        
        Returns:
            Tuple[pd.DataFrame, List[Dict]]: Interaction matrix, all interactions list
        """
        print("Analyzing agent interaction networks...")
        
        connections = defaultdict(lambda: defaultdict(int))
        all_interactions = []
        
        # Extract agent mentions from diaries
        for day_key, agent_texts in self.agent_texts.items():
            for agent in self.config.agents:
                if agent not in agent_texts:
                    continue
                
                text = agent_texts[agent].lower()
                
                # Count mentions of other agents
                for other_agent in self.config.agents:
                    if agent != other_agent:
                        mentions = text.count(other_agent.lower())
                        if mentions > 0:
                            connections[agent][other_agent] += mentions
                            all_interactions.append({
                                'day': day_key,
                                'agent1': agent,
                                'agent2': other_agent,
                                'mentions': mentions
                            })
        
        # Create interaction matrix
        interaction_matrix = pd.DataFrame(
            index=self.config.agents, 
            columns=self.config.agents, 
            data=0
        )
        
        for agent1 in self.config.agents:
            for agent2 in self.config.agents:
                if agent1 != agent2:
                    interaction_matrix.loc[agent1, agent2] = connections[agent1][agent2]
        
        # Save results
        interaction_matrix.to_csv(os.path.join(self.config.results_dir, 'agent_interaction_matrix.csv'))
        
        # Create visualizations
        self._create_network_visualizations(interaction_matrix, connections)
        
        return interaction_matrix, all_interactions
    
    def _create_network_visualizations(self, interaction_matrix: pd.DataFrame, connections: Dict) -> None:
        """Create and save network analysis visualizations."""
        # Network graph
        plt.figure(figsize=(12, 10))
        G = nx.DiGraph()
        
        # Add nodes and edges
        for agent in self.config.agents:
            G.add_node(agent)
        
        for agent1 in self.config.agents:
            for agent2 in self.config.agents:
                if agent1 != agent2 and connections[agent1][agent2] > 0:
                    G.add_edge(agent1, agent2, weight=connections[agent1][agent2])
        
        # Layout and drawing
        pos = nx.spring_layout(G, k=2, iterations=50, seed=42)
        
        # Draw nodes
        nx.draw_networkx_nodes(
            G, pos, 
            node_color='lightblue', 
            node_size=2000, 
            alpha=0.8
        )
        
        # Draw edges with varying thickness
        edges = G.edges()
        if edges:
            weights = [G[u][v]['weight'] for u, v in edges]
            max_weight = max(weights) if weights else 1
            
            nx.draw_networkx_edges(
                G, pos, 
                width=[w/max_weight * 5 for w in weights],
                alpha=0.6, 
                edge_color='gray', 
                arrows=True,
                arrowsize=20
            )
        
        # Draw labels
        nx.draw_networkx_labels(G, pos, font_size=12, font_weight='bold')
        
        plt.title(
            'Agent Interaction Network\n(Edge thickness = interaction frequency)', 
            size=16, 
            fontweight='bold'
        )
        plt.axis('off')
        plt.tight_layout()
        
        plt.savefig(
            os.path.join(self.config.results_dir, 'agent_network_graph.png'), 
            dpi=300, 
            bbox_inches='tight'
        )
        plt.close()
        
        # Interaction heatmap
        plt.figure(figsize=(10, 8))
        sns.heatmap(
            interaction_matrix.astype(int), 
            annot=True, 
            cmap='Blues', 
            fmt='d',
            cbar_kws={'label': 'Number of Mentions'}
        )
        plt.title('Agent Interaction Frequency Matrix', fontsize=16, fontweight='bold')
        plt.xlabel('Mentioned Agent', fontsize=12)
        plt.ylabel('Mentioning Agent', fontsize=12)
        plt.tight_layout()
        
        plt.savefig(
            os.path.join(self.config.results_dir, 'interaction_heatmap.png'), 
            dpi=300, 
            bbox_inches='tight'
        )
        plt.close()
    
    def generate_comprehensive_report(self) -> List[str]:
        """
        Generate a comprehensive text report summarizing all analyses.
        
        Returns:
            List[str]: Report lines for display or further processing
        """
        print("Generating comprehensive analysis report...")
        
        report_lines = []
        report_lines.extend([
            "=" * 80,
            "NARRATIVE ANALYSIS COMPREHENSIVE REPORT",
            "=" * 80,
            f"Analysis Date: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Total Days Analyzed: {len(self.agent_texts)}",
            f"Agents: {', '.join([agent.title() for agent in self.config.agents])}",
            f"TextBlob Available: {self.textblob_available}",
            ""
        ])
        
        try:
            # Load analysis results
            similarity_df = pd.read_csv(os.path.join(self.config.results_dir, 'diary_story_similarity.csv'))
            sentiment_df = pd.read_csv(os.path.join(self.config.results_dir, 'sentiment_behavior_analysis.csv'))
            
            # Diary-Story Similarity Analysis
            report_lines.extend([
                "1. DIARY-STORY SIMILARITY ANALYSIS",
                "-" * 40
            ])
            
            avg_similarity = similarity_df['similarity'].mean()
            report_lines.append(f"Overall Average Similarity: {avg_similarity:.3f}")
            
            agent_avg = similarity_df.groupby('agent')['similarity'].mean().sort_values(ascending=False)
            report_lines.append("\nAgent Rankings (by average similarity to daily stories):")
            for i, (agent, score) in enumerate(agent_avg.items(), 1):
                report_lines.append(f"{i}. {agent.title()}: {score:.3f}")
            
            # Sentiment Analysis
            report_lines.extend([
                "\n2. SENTIMENT ANALYSIS",
                "-" * 40
            ])
            
            agent_sentiment = sentiment_df.groupby('agent')['sentiment_polarity'].mean().sort_values(ascending=False)
            report_lines.append("Agent Rankings (by average sentiment):")
            for i, (agent, score) in enumerate(agent_sentiment.items(), 1):
                sentiment_label = "Positive" if score > 0.1 else "Negative" if score < -0.1 else "Neutral"
                report_lines.append(f"{i}. {agent.title()}: {score:.3f} ({sentiment_label})")
            
            # Behavioral Patterns
            behavior_cols = ['positive_emotions', 'negative_emotions', 'social_behavior', 'work_behavior']
            report_lines.extend([
                "\n3. BEHAVIORAL PATTERN ANALYSIS",
                "-" * 40
            ])
            
            for behavior in behavior_cols:
                if behavior in sentiment_df.columns:
                    top_agents = sentiment_df.groupby('agent')[behavior].mean().sort_values(ascending=False).head(3)
                    behavior_name = behavior.replace('_', ' ').title()
                    report_lines.append(f"\nTop 3 agents for {behavior_name}:")
                    for agent, score in top_agents.items():
                        report_lines.append(f"  {agent.title()}: {score:.1f} avg mentions")
            
            # Summary Statistics
            report_lines.extend([
                "\n4. SUMMARY STATISTICS",
                "-" * 40,
                f"Total diary entries analyzed: {len(sentiment_df)}",
                f"Average words per entry: {sentiment_df['word_count'].mean():.1f}",
                f"Average sentences per entry: {sentiment_df['sentence_count'].mean():.1f}",
                f"Days with complete data: {similarity_df['day'].nunique()}",
            ])
            
        except FileNotFoundError:
            report_lines.append("Warning: Some analysis files not found. Please run full analysis first.")
        except Exception as e:
            report_lines.append(f"Warning: Report generation error: {e}")
        
        report_lines.extend([
            "\n" + "=" * 80,
            "END OF REPORT",
            "=" * 80
        ])
        
        # Save report
        report_path = os.path.join(self.config.results_dir, 'comprehensive_report.txt')
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report_lines))
        
        return report_lines
    
    def run_complete_analysis(self) -> None:
        """
        Execute the complete narrative analysis pipeline.
        
        This method runs all analysis components in sequence and generates
        all output files and visualizations.
        """
        print("Starting comprehensive narrative analysis pipeline...")
        print("=" * 60)
        
        try:
            # Load simulation data
            self.load_simulation_data()
            
            # Run all analysis components
            print("\nExecuting analysis components:")
            
            similarity_results = self.analyze_diary_story_similarity()
            print("✓ Diary-story similarity analysis complete")
            
            consistency_results = self.analyze_day_consistency()
            print("✓ Day consistency analysis complete")
            
            sentiment_results = self.analyze_sentiment_and_behavior()
            print("✓ Sentiment and behavior analysis complete")
            
            routine_results = self.analyze_routine_patterns()
            print("✓ Routine pattern analysis complete")
            
            connection_results = self.analyze_agent_connections()
            print("✓ Agent connection analysis complete")
            
            # Generate comprehensive report
            report_lines = self.generate_comprehensive_report()
            print("✓ Comprehensive report generated")
            
            print("\n" + "=" * 60)
            print("ANALYSIS COMPLETE!")
            print(f"Results saved to: {self.config.results_dir}")
            print("\nGenerated files:")
            print("• diary_story_similarity.csv & heatmap")
            print("• agent_day_consistency.csv & heatmap") 
            print("• sentiment_behavior_analysis.csv & plots")
            print("• routine_analysis.csv & patterns")
            print("• agent_interaction_matrix.csv & network graph")
            print("• comprehensive_report.txt")
            print("=" * 60)
            
        except Exception as e:
            print(f"\nERROR: Analysis failed: {e}")
            print("Please check your data files and configuration.")
            raise


def main():
    """
    Main execution function for the narrative analyzer.
    
    Initializes the analyzer with default configuration and runs
    the complete analysis pipeline.
    """
    try:
        # Initialize analyzer with default configuration
        analyzer = NarrativeAnalyzer()
        
        # Run complete analysis
        analyzer.run_complete_analysis()
        
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()