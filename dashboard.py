
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

# load data
# streamlit to cache the loaded data, so that not to load data everytime loading the page
@st.cache_data
def load_data():
    df_agg = pd.read_csv('Aggregated_Metrics_By_Video.csv').iloc[1:,:]
    # remove non ascii character from column names
    df_agg.columns = df_agg.columns.str.encode('ascii', 'ignore').str.decode('ascii')
    # preprocessing df_agg
    preprocessing_dict = {
        # convert video publish time to datetime object
        "Video publish time": pd.to_datetime(df_agg['Video publish time'], format = '%b %d, %Y'),
        # Convert view duration from str with H:M:S format to datetime object 
        "Average view duration": pd.to_datetime(df_agg['Average view duration'], format ='%H:%M:%S'),
        # Get average duration in seconds
        "Avg_duration_sec": lambda y: y["Average view duration"]\
                                .apply(lambda x: x.second + x.minute*60 + x.hour * 3600),
        # sum all engagements and divide by number of views to get engagement ratio
        'Engagement_ratio': lambda x: (x['Comments added'] + x['Shares'] + x['Dislikes'] + x['Likes']) / x['Views'],
        # get the ratio of views to subscribtion gained
        'Views / sub gained': lambda x: x['Views'] / x['Subscribers gained']
    }
    df_agg = df_agg.assign(**preprocessing_dict)
    # sort values by video publish time
    df_agg.sort_values("Video publish time", ascending = False, inplace = True)

    df_agg_sub = pd.read_csv('./Aggregated_Metrics_By_Country_And_Subscriber_Status.csv')
    # df_comments = pd.read_csv('./All_Comments_Final.csv')
    df_time = pd.read_csv('./Video_Performance_Over_Time.csv')
    # convert date to datetime object
    df_time['Date'] = pd.to_datetime(df_time['Date'])
    return df_agg, df_agg_sub, df_time

df_agg, df_agg_sub, df_time = load_data()

df_time = df_time.merge(df_agg.loc[:, ["Video", "Video publish time"]], left_on = 'External Video ID',
                            right_on = 'Video')
df_time = df_time.assign(
    days_published = lambda x: (x['Date'] - x['Video publish time']).dt.days
)

metric_date_12mo = df_agg['Video publish time'].max() - pd.DateOffset(months = 12)

df_time = df_time.query('`Video publish time` >= @metric_date_12mo')

views_days = pd.pivot_table(df_time,
                            index = 'days_published',
                            values = 'Views',
                            aggfunc = [np.mean, np.median, 
                                        lambda x: np.percentile(x, 80),
                                        lambda x: np.percentile(x, 20)]).reset_index()
views_days.columns = ['days_published', 'mean_views', 'median_views',
                        '80pct_views', '20pct_views']
views_days = views_days[views_days['days_published'].between(0, 30)]
views_cumulative = views_days.loc[:, views_days.columns]
views_cols = views_days.columns.tolist()[1:]
views_cumulative.loc[:, views_cols] = views_cumulative.loc[:, views_cols].cumsum()

def style_negative(v, props = ''):
    if isinstance(v, (int, float)):
        return props if v < 0 else None

def style_positive(v, props = ''):
    if isinstance(v, (int, float)):
        return props if v > 0 else None
    
def audience_simple(country):
    if country == 'US':
        return 'USA'
    elif country == 'IN':
        return 'India'
    # elif country == 'DE':
    #     return 'Germany'
    # elif country == 'GB':
    #     return 'United Kingdom'
    # elif country == 'CA':
    #     return 'Canada'
    # elif country == 'BR':
    #     return 'Brazil'
    # elif country == 'ES':
    #     return 'Spain'
    else:
        return 'Other'

# build dashboard
# add sidebar
add_sidebar = st.sidebar.selectbox('Aggregate or Individual Video',
                                   ('Aggregate Metrics', 'Individual Video Analysis'))
# show individual metrics
if add_sidebar == 'Aggregate Metrics':
    st.header('Ken Jee YouTube Aggregated Data')
    included_metrics = ['Video publish time', 'Views', 'Likes', 'Subscribers', 'Shares',
                        'Comments added', 'RPM (USD)', 'Average percentage viewed (%)', 
                        'Avg_duration_sec', 'Engagement_ratio', 'Views / sub gained']
    df_agg_metrics = df_agg[included_metrics]
    metric_date_6mo = df_agg_metrics['Video publish time'].max() - pd.DateOffset(months = 6)
    metric_date_12mo = df_agg_metrics['Video publish time'].max() - pd.DateOffset(months = 12)
    metric_medians6mo = df_agg_metrics.query('`Video publish time` >= @metric_date_6mo').median(numeric_only=True)
    metric_medians12mo = df_agg_metrics.query('`Video publish time` >= @metric_date_12mo').median(numeric_only=True)

    columns = st.columns(5)

    for i, m in enumerate(metric_medians6mo.index):
        count = i % 5
        with columns[count]:
            delta = (metric_medians6mo[i] - metric_medians12mo[i]) / metric_medians12mo[i]
            st.metric(label = m,
                      value = round(metric_medians6mo[i], 1), 
                      delta = f"{delta:.2%}")

    # showing table to display metrics in details
    df_agg_numeric = df_agg.select_dtypes(include = [np.number])
    df_agg_numeric = (df_agg_numeric - metric_medians12mo).div(metric_medians12mo)
    df_agg_diff = pd.concat([df_agg_numeric, df_agg.select_dtypes(exclude = np.number)], axis = 1)
    df_agg_diff['Publish_date'] = df_agg_diff['Video publish time'].dt.date
    included_cols = ["Video title", "Publish_date"] + included_metrics[1:]
    df_agg_diff = df_agg_diff.reset_index().loc[:, included_cols]

    st.dataframe(df_agg_diff.style.applymap(style_negative, props='color:red;')
                 .applymap(style_positive, props='color:green;')
                 .format('{:.1%}', subset = included_metrics[1:]))
    
if add_sidebar == 'Individual Video Analysis':
    videos = df_agg.loc[df_agg["Video"].isin(df_time['Video']) , 'Video title']
    st.header('Individual Video Performance')
    video_select = st.selectbox('Pick a Video', videos)

    agg_filtered = df_agg.query('`Video title` == @video_select')
    agg_sub_filtered = df_agg_sub.query('`Video Title` == @video_select')
    agg_sub_filtered= agg_sub_filtered.assign(Country = lambda x: x['Country Code'].apply(audience_simple))
    agg_sub_filtered.sort_values(['Is Subscribed', 'Country'], inplace = True)

    fig = px.bar(agg_sub_filtered, x = "Views", y = "Is Subscribed",
                 color = "Country", orientation="h")
    st.plotly_chart(fig)

    agg_time_filtered = df_time.query('`Video Title` == @video_select')
    first_30 = agg_time_filtered[agg_time_filtered['days_published'].between(0, 30)]
    first_30 = first_30.sort_values('days_published')

    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x = views_cumulative['days_published'], y = views_cumulative['20pct_views'],
                   mode = 'lines',
                   name = '20th percentile',
                   line = dict(color='purple', dash = 'dash')))
    fig2.add_trace(go.Scatter(x = views_cumulative['days_published'], y = views_cumulative['median_views'],
                   mode = 'lines',
                   name = '50th percentile',
                   line = dict(color='black', dash = 'dash')))
    fig2.add_trace(go.Scatter(x = views_cumulative['days_published'], y = views_cumulative['80pct_views'],
                   mode = 'lines',
                   name = '80th percentile',
                   line = dict(color='royalblue', dash = 'dash')))
    fig2.add_trace(go.Scatter(x = first_30['days_published'], y = first_30['Views'].cumsum(),
                   mode = 'lines',
                   name = 'Current Video',
                   line = dict(color='firebrick', width = 8)))
    fig2.update_layout(title = 'View Comparison first 30 days',
                       xaxis_title = 'Days Since Published',
                       yaxis_title = 'Cumulative views')

    st.plotly_chart(fig2)














