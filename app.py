import re
import streamlit as st
import preprocessor,helper
from wordcloud import WordCloud
st.sidebar.title("WhatsApp Analysis")
st.title("Note: This app is still in development and may not work as expected.")
uploaded_file = st.sidebar.file_uploader("Upload your WhatsApp chat()", type="txt")

if uploaded_file is not None:
    data = uploaded_file.read().decode("utf-8")
    df = preprocessor.preprocess(data)
    
    st.dataframe(df)
    options = []
    options.extend(df['Name'].unique())
    options = [name for name in options if ',' not in str(name)]
  
    options.sort()
    options.insert(0,'Overall')
    
    
    selected_user = st.sidebar.selectbox("Select a user", options)
    stats,cleaned_df,links = helper.fetch_stats(selected_user,df)

    if st.sidebar.button("Show Analysis"):
        
        col1,col2,col3,col4 = st.columns(4)
        with col1:
           
            st.metric(label="Total Messages", value=stats[0])
        with col2:
           
            st.metric(label="Total Words", value=stats[1])
        with col3:
           
            st.metric(label="Total Media Shared", value=stats[2])
        with col4:
            
            st.metric(label="Total Links Shared", value=stats[3])

        helper.fetch_wordcloud(cleaned_df, links)
    
        helper.fetch_most_busy_users(df)
        helper.most_common_words(cleaned_df,links)
        helper.fetch_emojis(cleaned_df)