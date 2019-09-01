import datetime

from lib.api import ApiDataLoader
from lib.model import Site, Group
from lib import util
from lib import yt_api_util
from lib.path_util import PathHelper

# parse data.txt
def parse(file_path):
    print("Parsing %s" % file_path)
    f = open(file_path)
    groups = []
    current_group = None
    for s in f.readlines():
        s = s.strip()
        if not s:
            continue
        if s.startswith("#"):
            if current_group:
                groups.append(current_group)
            current_group = Group(title = s[1:].strip(), ids = [])
            continue

        current_group.ids.append(util.extract_youtube_id(s))
    if current_group: 
        groups.append(current_group)
        
    return groups
 
def parse_skip_file(file_path):
    f = open(file_path)
    return [line.strip() for line in f.readlines() if line.strip()]

def process_groups(groups, video_data):
    # merge all groups with less than 2 vid to Others
    result = []
    others = []
    for group in groups:
        if len(group.ids) <= 2:
            others += group.ids
        else:
            result.append(group)
    if len(others) > 0:
        result.append(Group('Others', others))

    # sort each group by publish date
    for group in result:
        group.ids = sort_video_ids_by_time(group.ids, video_data)
    
    return result

def sort_video_ids_by_time(ids, video_data):
    return sorted(
        ids,
        key=lambda id: video_data[id].published_at, 
        reverse=True)

def load_cache():
    cache_files = util.get_cache_json_files()
    data = {}
    for id in cache_files:
        file_path = util.get_cache_json_path(id)
        data[id] = yt_api_util.read_single_video_json(file_path)
    return data

def load_video_data(ids, api_key):
    print("Load video data")
    all_data = load_cache()
    need_fetch = [id for id in ids if not id in all_data.keys()]
    data = {id:all_data[id] for id in ids if id in all_data}

    if len(need_fetch) > 0:
        if api_key is None:
            print("Set api key to fetch data")
        else:
            print("Start fetching %s video data" % len(need_fetch))
            data_loader = ApiDataLoader(api_key)
            fetched_data = data_loader.fetch_all(need_fetch)
            data.update(fetched_data)
  
    return data

def filter_video_by_date(video_data, start_date, end_date):
    result = []
    for id,v in video_data.items():
        if start_date <= v.published_at and v.published_at < end_date:
            result.append(id)
    return sort_video_ids_by_time(result, video_data)

def group_by_time(video_data):
    dummy_start_date = datetime.date(2017, 7, 1)
    start_date = datetime.date(2019, 7, 1)
    today = datetime.date.today()
    week = datetime.timedelta(weeks=1)

    prev_videos = Group(
        "Previous Videos",
        filter_video_by_date(video_data, dummy_start_date, start_date)
    )
    groups = [prev_videos]

    while start_date <= today:
        end_date = start_date + week
        title = "Week %s" % start_date
        ids = filter_video_by_date(video_data, start_date, end_date)
        group = Group(title, ids) 

        if len(group.ids) > 0:
            groups.insert(0, group)
        start_date = end_date
    return groups

def load_site_data(config, path="data/en", api_key = None):
    ph = PathHelper(path)

    groups = parse(ph.get_data_file())
    most_viewed_data = parse(ph.get_most_viewed_data_file())
    latest_data = parse(ph.get_latest_data_file())

    if len(most_viewed_data) > 0:
        most_viewed = most_viewed_data[0].ids
    else:
        most_viewed = []

    if len(latest_data) > 0:
        latest = latest_data[0].ids
    else:
        latest = []

    all_youtube_ids = [id for g in groups for id in g.ids]
    print("Num of videos: %s" % len(all_youtube_ids))

    video_data = load_video_data(all_youtube_ids, api_key)

    # merge and sort
    groups = process_groups(groups, video_data)

    site = Site()
    site.groups = groups
    site.video_data = video_data
    site.most_viewed = most_viewed
    site.latest = latest
    site.groups_by_time = group_by_time(video_data)
    return site

def load_skip_ids(config):
    return parse_skip_file(config.get_skip_file())

def sort_videos(video_data):
    ids = video_data.keys()
    most_viewed = sorted(ids, key=lambda id: -int(video_data[id].view_count))
    latest = sorted(ids, key=lambda id: video_data[id].published_at, reverse=True)

    return (most_viewed, latest)
