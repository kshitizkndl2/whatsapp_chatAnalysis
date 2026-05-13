import re
import matplotlib.pyplot as plt
from numpy import size
import pandas as pd
import streamlit as st
from urlextract import URLExtract
from wordcloud import WordCloud

extract = URLExtract()


def _word_count_excluding_links(message, links_longest_first):
    if pd.isna(message):
        return 0
    s = str(message)
    for url in links_longest_first:
        if url in s:
            s = s.replace(url, " ")
    return len(s.split())
def fetch_stats(name,df):
    if name != 'Overall':
        system_pattern = re.compile(
    r"""
    (missed\s+)?(video|voice)\s+call.*
    | video\s+omitted
    | image\s+omitted
    | audio\s+omitted
    | gif\s+omitted
    | sticker\s+omitted
    | media\s+omitted

    | \S+\.(pdf|docx?|pptx?|xlsx?|jpg|png|jpeg)\s*[•·●]\s*\d+\s+pages?\s+document\s+omitted
    | \S+\s+document\s+omitted

    | waiting\s+for\s+this\s+message.*


    | answered\s+on\s+other\s+device
    | no\s+answer

    | .*added\s+you
    | .*created(\s+this)?\s+group
    | .*joined.*
    | .*left.*
    | .*removed.*

    | .*end-to-end\s+encrypted.*   # 🔥 FIXED (loose match)

    """,
    re.IGNORECASE | re.VERBOSE
)

        df_cleaned = df[df['Name'] == name]
        df_cleaned = df_cleaned[~df_cleaned["Message"].str.contains(system_pattern, na=False)].reset_index(drop=True)
        lst = []
        cleaned_names = df[df['Name'] == name]['Name']
        cleaned_names = [name for name in cleaned_names if ',' not in str(name)]
        total_messages = len(cleaned_names)
        links = []
        for message in df_cleaned['Message']:
            links.extend(extract.find_urls(message))
        link_count = len(links)
        links_for_strip = sorted(set(links), key=len, reverse=True)
        media_pattern = r"(video|image|audio|gif|sticker|document|media) omitted"
        media_count = df[df['Name'] == name]["Message"].str.contains(media_pattern, case=False, regex=True).sum()
        total_words = int(
            df_cleaned["Message"]
            .apply(lambda m: _word_count_excluding_links(m, links_for_strip))
            .sum()
        )
        
        lst.append(total_messages)
        lst.append(total_words)
        lst.append(media_count)
        lst.append(link_count)

        return lst, df_cleaned,links
    else:
        lst = []
        system_pattern = re.compile(
    r"""
    (missed\s+)?(video|voice)\s+call.*
    | video\s+omitted
    | image\s+omitted
    | audio\s+omitted
    | gif\s+omitted
    | sticker\s+omitted
    | media\s+omitted

    | \S+\.(pdf|docx?|pptx?|xlsx?|jpg|png|jpeg)\s*[•·●]\s*\d+\s+pages?\s+document\s+omitted
    | \S+\s+document\s+omitted

    | waiting\s+for\s+this\s+message.*


    | answered\s+on\s+other\s+device
    | no\s+answer

    | .*added\s+you
    | .*created(\s+this)?\s+group
    | .*joined.*
    | .*left.*
    | .*removed.*

    | .*end-to-end\s+encrypted.*   # 🔥 FIXED (loose match)

    """,
    re.IGNORECASE | re.VERBOSE
)

    df_cleaned = df[~df["Message"].str.contains(system_pattern, na=False)].reset_index(drop=True)
    cleaned_names = df['Name']
    cleaned_names = [name for name in cleaned_names if ',' not in str(name)]
            
    total_messages = len(cleaned_names)
    links = []
    for message in df['Message']:
            links.extend(extract.find_urls(message))
    link_count = len(links)
    links_for_strip = sorted(set(links), key=len, reverse=True)
    total_words = int(
        df_cleaned["Message"]
        .apply(lambda m: _word_count_excluding_links(m, links_for_strip))
        .sum()
    )
    media_pattern = r"(video|image|audio|gif|sticker|document|media) omitted"

    media_count = df["Message"].str.contains(media_pattern, case=False, regex=True).sum()
    

        
    lst.append(total_messages)
    lst.append(total_words)
    lst.append(media_count)
    lst.append(link_count)
      
    return lst,df_cleaned,links

def fetch_wordcloud(wordcloud_df, links):
    st.title("Word Cloud of Links Shared")
    if links:
        words = " ".join(" ".join(links).split(','))
        wc = WordCloud(width=800, height=800, background_color='black').generate(words)
        st.image(wc.to_array())
    else:
        st.write("No links shared")
    st.title("Word Cloud of Words Shared")
    if len(wordcloud_df['Message'].values) > 0:
        words = wordcloud_df['Message'].values
        words = [word for word in words if not any(link in str(word) for link in links)]
        if len(words) > 0:
            words = " ".join(" ".join(words).split('],['))
            wc = WordCloud(width=800, height=800, background_color='black').generate(words)
            st.image(wc.to_array())
        else:
            st.write("No words shared")
    else:
        st.write("No words shared")
def fetch_most_busy_users(df):
    st.title("Most Busy Users")
    df = df.copy()
    df = df[~df['Name'].astype(str).str.contains(',', na=False)]
    x = df['Name'].value_counts().head(5)
    name = x.index
    count = x.values
    fig, ax = plt.subplots()
    plt.xticks(rotation=45)
    ax.bar(name, count) 
    plt.xlabel("Users")
    plt.ylabel("Count")
    plt.title("Most Busy Users")
    plt.show()
    st.pyplot(fig)
    
    

