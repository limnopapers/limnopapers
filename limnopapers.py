import feedparser
import pandas as pd
import datetime
import twitter
import twitter_api

def filter_limno(df):
    filter_for = ['lake', "reservoir"] 
    mentions_limno = df['summary'].str.contains('|'.join(filter_for)) | df['title'].str.contains('|'.join(filter_for))

    filter_against = ['ocean']
    mentions_junk = df['summary'].str.contains('|'.join(filter_against))
    
    return(df.drop(df[mentions_limno == False & mentions_junk].index.values))

def filter_today(df, day):
    published_today = (df['updated'] > datetime.datetime.strptime(day, "%Y-%m-%d") - datetime.timedelta(days = 0.5)) & (df['updated'] < datetime.datetime.strptime(day, "%Y-%m-%d") + datetime.timedelta(days = 0.5))     
    return(df.drop(df[published_today == False].index.values))

def get_posts(day = str(datetime.date.today())):
    # https://stackoverflow.com/questions/45701053/get-feeds-from-feedparser-and-import-to-pandas-dataframe
    rawrss = [
        'http://onlinelibrary.wiley.com/rss/journal/10.1002/(ISSN)1939-5590',
        'http://onlinelibrary.wiley.com/rss/journal/10.1002/(ISSN)2378-2242',        
        'https://www.journals.uchicago.edu/action/showFeed?type=etoc&feed=rss&jc=fws',
        'https://www.tandfonline.com/action/showFeed?type=etoc&feed=rss&jc=tinw20',
        'http://onlinelibrary.wiley.com/rss/journal/10.1111/(ISSN)1365-2427',
        'http://onlinelibrary.wiley.com/rss/journal/10.1002/(ISSN)1944-7973',
        'http://onlinelibrary.wiley.com/rss/journal/10.1002/(ISSN)2169-8961',
        'http://onlinelibrary.wiley.com/rss/journal/10.1002/(ISSN)1099-1085',
        'http://onlinelibrary.wiley.com/rss/journal/10.1002/(ISSN)1939-5582'                
        ]

    posts = []
    for url in rawrss:
        feed = feedparser.parse(url)
        for post in feed.entries:
            posts.append((post.title, post.summary, post.link, post.dc_source, post.updated))

    return(posts)

def get_papers(day = str(datetime.date.today())):
    posts = get_posts(day = day)
    res = pd.DataFrame(posts)
    res.columns = ['title', 'summary', 'prism_url', 'dc_source', 'updated']
    res['updated'] = pd.to_datetime(res['updated'])
    res = res.sort_values(by = ['updated'])
    res = filter_limno(res)
    res = filter_today(res, day)
    # res.to_csv("test.csv")

    return(res)

def limnotoots(event, context):
    # api = twitter.Api(consumer_key='', consumer_secret='', access_token_key='',	access_token_secret='')
    api = twitter_api.api()    
    # print(api.VerifyCredentials())

    data = get_papers()        
    toots = data['title'] + ". " + data['dc_source']  + ". " + data['prism_url']    
    
    for toot in toots:
        # print(toot)
        status = api.PostUpdate(toot)        

