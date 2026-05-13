import re
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from urlextract import URLExtract
from wordcloud import WordCloud
import nltk
nltk.download('stopwords')
from nltk.corpus import stopwords
from collections import Counter

import regex

extract = URLExtract()

_WHATSAPP_TAIL_TAGS = re.compile(
    r"(?:\s*<This message was edited>|\s*<This message was deleted>)+$",
    re.IGNORECASE,
)


def _strip_whatsapp_message_suffixes(text) -> str:
    """Remove trailing WhatsApp export tags (e.g. ``<This message was edited>``)."""
    if pd.isna(text):
        return ""
    s = str(text).strip()
    while True:
        prev = s
        s = _WHATSAPP_TAIL_TAGS.sub("", s).rstrip()
        if s == prev:
            break
    return s


def _extract_emojis_from_string(s: str) -> list[str]:
    """Grapheme-aware emoji extraction (no third-party ``emoji`` package)."""
    if not s:
        return []
    found: list[str] = []
    for cluster in regex.findall(r"\X", s, regex.V1):
        if regex.search(r"\p{Extended_Pictographic}", cluster):
            found.append(cluster)
    return found


def _word_count_excluding_links(message, links_longest_first):
    if pd.isna(message):
        return 0
    s = str(message)
    for url in links_longest_first:
        if url in s:
            s = s.replace(url, " ")
    return len(s.split())


def fetch_stats(name, df):
    df = df.copy()
    df["Message"] = df["Message"].apply(_strip_whatsapp_message_suffixes)

    if name != "Overall":
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
        stop_words = stopwords.words('english')
        words = wordcloud_df['Message'].values
        words = [word for word in words if not any(link in str(word) for link in links)]
        words = [word for word in words if word not in stop_words]
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
    df = df[~df["Name"].astype(str).str.contains(",", na=False)]
    counts = df["Name"].value_counts().head(5)
    total = len(df)
    if total == 0 or counts.empty:
        st.write("No messages to plot.")
        return

    names = counts.index.tolist()
    vals = counts.values
    n = len(names)
    fig, ax = plt.subplots(figsize=(10, max(4.0, n * 0.65)))
    y_pos = range(n)
    bars = ax.barh(y_pos, vals, color="steelblue")
    ax.set_yticks(y_pos, labels=names)
    ax.invert_yaxis()
    ax.set_xlabel("Messages sent")
    ax.set_ylabel("User")
    ax.set_title("Most busy users — % of all messages in this chat")
    ax.margins(x=0.18)
    pct_labels = [f"{100 * v / total:.1f}%" for v in vals]
    ax.bar_label(bars, labels=pct_labels, padding=4, fontsize=10)
    fig.tight_layout()
    st.pyplot(fig, clear_figure=True)
    plt.close(fig)
def most_common_words(df,links):
    st.title("Most Common Words")
    stop_words = stopwords.words('english')
    words = df['Message'].values
    words = [word for word in words if not any(link in str(word) for link in links)]
    unique_words = list(set(words))
    if len(unique_words) > 0:
        words = " ".join(" ".join(words).split('],['))
        words = words.split()
        word_counts = Counter(words)
        most_common_words = word_counts.most_common(10)
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.barh(range(len(most_common_words)), [count for word, count in most_common_words], align='center')
        ax.set_yticks(range(len(most_common_words)))
        ax.set_yticklabels([word for word, count in most_common_words])
        ax.invert_yaxis()
        ax.set_xlabel('Frequency')
        ax.set_title('Most Common Words')
        st.pyplot(fig, clear_figure=True)
        plt.close(fig)
    else:
        st.write("No words to plot.")
def fetch_emojis(df):
    all_emojis = []
    for message in df["Message"].astype(str):
        all_emojis.extend(_extract_emojis_from_string(message))
    if not all_emojis:
        st.write("No emojis found.")
        return
    most_common = Counter(all_emojis).most_common(12)
    glyphs = [e for e, _ in most_common]
    counts = [c for _, c in most_common]

    fig, ax = plt.subplots(figsize=(9, 9))
    _wedges, texts, autotexts = ax.pie(
        counts,
        labels=glyphs,
        autopct="%1.1f%%",
        startangle=90,
        counterclock=False,
        pctdistance=0.75,
        labeldistance=1.05,
        textprops={"fontsize": 16},
    )
    plt.setp(autotexts, fontsize=10)
    ax.set_title("Most common emojis")
    fig.tight_layout()
    st.pyplot(fig, clear_figure=True)
    plt.close(fig)




