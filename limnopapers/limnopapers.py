import os
import sys
import textwrap
import inspect
import feedparser
import webbrowser
import pandas as pd
import datetime
import twitter
from colorama import Fore
import argparse
import pkg_resources
import re

sys.path.append(".")
import limnopapers.utils as utils


currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
sys.path.insert(0, parentdir)

try:
    import config
except:
    print("No twitter keys found")


def toot_split(toot):
    # toot = "asdf? ddd. ppp"
    # toot = "Annual 30-meter Dataset for  Glacial Lakes in High Mountain  Asia from 2008 to 2017. Earth System Science Data. https://doi.org/10.5194/essd-2020-57"
    res = re.split("\\. |\\? ", toot)
    prism_url = res[len(res) - 1]
    dc_source = res[len(res) - 2]
    title = ". ".join(res[0 : len(res) - 2])
    return [title, dc_source, prism_url]


def filter_limno(df):
    r"""Filter limnology themed papers from a pandas DataFrame.
    :param df: pandas DataFrame with 'title' and 'summary' columns
    """

    keywords = pd.read_csv(
        pkg_resources.resource_filename("limnopapers", "keywords.csv")
    )
    filter_for = keywords["filter_for"].tolist()
    filter_for = [x for x in filter_for if str(x) != "nan"]
    filter_against = keywords["filter_against"].tolist()

    df = df.reset_index(drop=True)
    # df = res
    # df = df.iloc[0:2]

    has_limno_title = df["title"].str.contains("|".join(filter_for), case=False)
    has_limno_summary = df["summary"].str.contains("|".join(filter_for), case=False)

    # save matching filter_for here

    is_limno = (
        pd.DataFrame([has_limno_title, has_limno_summary]).transpose().sum(axis=1) > 0
    )

    df = df[is_limno]

    has_junk_summary = ~df["summary"].str.contains("|".join(filter_against), case=False)
    has_junk_title = ~df["title"].str.contains("|".join(filter_against), case=False)

    # save matching filter_against here
    if len(df.index) > 0:
        filter_against = keywords["filter_against"][
            keywords["filter_against"]
            .apply(lambda x: df["summary"].str.contains(x, case=False))
            .iloc[:, 0]
        ]

    not_junk = (
        pd.DataFrame([has_junk_summary, has_junk_title]).transpose().sum(axis=1) == 2
    )

    return {"papers": df[not_junk], "filter_against": filter_against}


def filter_today(df, day):
    today_parsed = datetime.datetime.strptime(day + " 09:00:00", "%Y-%m-%d %H:%M:%S")
    yesterday = today_parsed - datetime.timedelta(days=1)
    tomorrow = today_parsed + datetime.timedelta(days=0)
    published_today = (df["updated"] > yesterday) & (df["updated"] < tomorrow)
    res_today = df[published_today]
    return res_today


def get_posts_(title, url, feed_dict=None):
    """
    title = "Limnology and Oceanography"
    url = "https://onlinelibrary.wiley.com/rss/journal/10.1002/(ISSN)1939-5590"
    """
    # print(url)
    if feed_dict is None:
        feed_dict = feedparser.parse(url)
    posts = []
    for post in feed_dict.entries:
        try:
            posts.append(
                (post.title, post.description_encoded, post.link, title, post.updated)
            )
        except AttributeError:
            try:
                posts.append((post.title, post.summary, post.link, title, post.updated))
            except AttributeError:
                try:
                    posts.append(
                        (post.title, post.summary, post.link, title, post.published)
                    )
                except AttributeError:
                    try:
                        posts.append((post.title, post.summary, post.link, title, None))
                    except AttributeError:
                        try:
                            posts.append((None, None, None, None, None))
                        except AttributeError:
                            pass

    res = pd.DataFrame(posts)
    # print(res.columns)
    # print(res)
    try:
        res.columns = ["title", "summary", "prism_url", "dc_source", "updated"]
        return res
    except Exception:
        pass


def get_posts():
    # check for internet
    if not utils.internet():
        raise Exception("limnopapers requires an internet connection.")

    # https://stackoverflow.com/questions/45701053/get-feeds-from-feedparser-and-import-to-pandas-dataframe
    rawrss = pd.read_csv(pkg_resources.resource_filename("limnopapers", "journals.csv"))

    # sort rawrss by increasing journal name nchar length for pretty printing
    rawrss.index = rawrss["title"].str.len()
    rawrss = rawrss.sort_index().reset_index(drop=True)

    posts = []
    for i in range(len(rawrss.index)):
        sys.stdout.write("\b" * 1000)
        sys.stdout.write("Fetching papers from: " + rawrss["title"][i] + "\r")

        try:
            single_posts = get_posts_(rawrss["title"][i], rawrss["rawrss"][i])
            posts.append(single_posts)
        except AttributeError:
            pass

    print("\n")
    return posts


def get_papers(to_csv=False, log_path="log.csv"):
    posts = get_posts()
    res = pd.concat(posts)
    res["updated"] = pd.to_datetime(res["updated"], utc=True).dt.tz_localize(None)
    res = res.sort_values(by=["updated"])
    res = res.drop_duplicates(subset=["title"], keep="first")
    if to_csv is not False:
        res.to_csv("test.csv")

    if os.path.exists(log_path):
        # rm entries that are also in log
        log = pd.read_csv(log_path)
        # filter out exact matches to log
        res = res[~res["title"].isin(log["title"])]
    res_limno = filter_limno(res)["papers"]

    titles = res_limno["title"].copy()
    titles[titles.str.len() > 159] = (
        titles[titles.str.len() > 159].str.slice(0, 159) + "..."
    )

    if os.path.exists(log_path):
        log = log[[isinstance(x, str) for x in log["title"]]]
        res_limno = res_limno[~titles.str.lower().isin(map(str.lower, log["title"]))]
        res_limno = filter_limno(res_limno)["papers"]

        # filter out punctuation missing matches to log
        titles = res_limno["title"].copy()
        titles_with_periods = titles.copy() + "."
        is_in_log = ~titles_with_periods.str.lower().isin(map(str.lower, log["title"]))
        res_limno = filter_limno(res_limno[is_in_log])["papers"]

        titles = res_limno["title"].copy()
        titles_with_qmarks = titles.copy() + "?"
        res_limno = filter_limno(
            res_limno[
                ~titles_with_qmarks.str.lower().isin(map(str.lower, log["title"]))
            ]
        )["papers"]

    if to_csv is not False:
        res_limno.to_csv("test_limno.csv")

    dfs = {}
    dfs["res"] = res
    dfs["res_limno"] = res_limno

    return dfs


def limnotoots(tweet, interactive, to_csv=False, browser=False, ignore_all=False):
    r"""Filter limnology themed papers from a pandas DataFrame.
    :param tweet: boolean. Post tweets of limnopapers
    :param interactive: boolean. Ask for approval before tweeting.
    :param to_csv: boolean. Save output to csv for debugging.
    :param browser: boolean. Open limnopapers in browser tabs.
    :param ignore_all: boolean. Write all toots to log, don't tweet.
    """

    data = get_papers(to_csv)
    filtered = data["res_limno"].reset_index(drop=True)
    data = filter_today(data["res"], day=str(datetime.date.today()))

    if len(data.index) != 0 or len(filtered.index) != 0:
        print(Fore.RED + "Excluded: ")
        print()
        toots = data["title"] + ". " + data["dc_source"] + ". " + data["prism_url"]
        for toot in toots:
            print(Fore.RED + toot)
            print()

        print(Fore.GREEN + "Filtered: ")
        print()
        titles = filtered["title"].copy()
        titles[titles.str.len() > 159] = (
            titles[titles.str.len() > 159].str.slice(0, 159) + "..."
        )

        # debugging snippet
        # df = pd.DataFrame(data={'title': ["1?", "none", "kkd"]})
        # titles = df['title'].copy()
        no_questionmark = titles.str.contains("[^?]$", regex=True)
        titles[no_questionmark] = titles[no_questionmark] + "."

        toots = titles + " " + filtered["dc_source"] + ". " + filtered["prism_url"]
        for toot in toots:
            print(Fore.GREEN + toot)
            print()

        if browser is True:
            for url in filtered["prism_url"]:
                webbrowser.open(url)

        if tweet is True or interactive is True:
            api = twitter.Api(
                consumer_key=config.consumer_key,
                consumer_secret=config.consumer_secret,
                access_token_key=config.access_token_key,
                access_token_secret=config.access_token_secret,
            )
            # print(api.VerifyCredentials())

            toots = toots.sample(frac=1)  # randomize toots order
            toots_n_max = 5
            toots_n = 0
            for toot in toots:
                print(toot)
                if interactive is True:
                    if ignore_all:
                        post_toot = "i"
                        posted = "i"
                    else:
                        post_toot = input("post limnotoot (y)/n/i? ") or "y"
                        if post_toot in ["y"]:
                            status = api.PostUpdate(toot)
                            posted = "y"
                        if post_toot in ["i"]:
                            posted = "i"

                    if post_toot in ["y", "i"]:
                        # write to log
                        if not os.path.exists("log.csv"):
                            pd.DataFrame(
                                [["", "", "", "", ""]],
                                columns=[
                                    "title",
                                    "dc_source",
                                    "prism_url",
                                    "posted",
                                    "date",
                                ],
                            ).to_csv("log.csv")
                        log = pd.read_csv("log.csv")
                        keys = ["title", "dc_source", "prism_url", "posted", "date"]

                        # toot = "title? journal. url"
                        # toot = "Annual 30-meter Dataset for  Glacial Lakes in High Mountain  Asia from 2008 to 2017. Earth System Science Data. https://doi.org/10.5194/essd-2020-57"
                        # posted = "y"
                        title, dc_source, prism_url = toot_split(toot)
                        date = str(datetime.date.today())
                        d = dict(zip(keys, [title, dc_source, prism_url, posted, date]))
                        d = pd.DataFrame.from_records(d, index=[0])
                        log = log.append(pd.DataFrame(data=d), ignore_index=True)
                        log.to_csv("log.csv", index=False)
                else:  # interactive is False
                    if toots_n < toots_n_max + 1:
                        status = api.PostUpdate(toot)
                        toots_n += 1

                        # write to log
                        log = pd.read_csv("log.csv")
                        keys = ["title", "dc_source", "prism_url"]
                        title, dc_source, prism_url = toot_split(toot)
                        d = dict(zip(keys, [title, dc_source, prism_url]))
                        d = pd.DataFrame.from_records(d, index=[0])
                        log = log.append(pd.DataFrame(data=d))
                        log.to_csv("log.csv", index=False)
                post_toot = "n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tweet", default=False, action="store_true")
    parser.add_argument("--interactive", default=False, action="store_true")
    parser.add_argument("--browser", default=False, action="store_true")
    parser.add_argument("--debug", default=False, action="store_true")
    args = parser.parse_args()

    limnotoots(
        tweet=args.tweet,
        interactive=args.interactive,
        browser=args.browser,
        to_csv=args.debug,
    )


if __name__ == "__main__":
    main()
