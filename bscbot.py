import praw, datetime, sys, json, traceback, numpy
from time import sleep
from dateutil.relativedelta import relativedelta

with open("config.json") as config_file:
    config_json = json.load(config_file)

    userAgent = config_json['userAgent']
    cID = config_json['cID']
    cSC = config_json['cSC']
    userN = config_json['userN']
    userP = config_json['userP']

    reddit = praw.Reddit(user_agent=userAgent, 
        client_id=cID, 
        client_secret=cSC, 
        username=userN, 
        password=userP)

    subreddit = reddit.subreddit(config_json['subreddit'])
    day_offset = config_json['day_offset']
    similarity = config_json['similarity']


data_dict = {}


# https://blog.paperspace.com/implementing-levenshtein-distance-word-autocomplete-autocorrect/
def levenshtein(token1, token2):

    distances = numpy.zeros((len(token1) + 1, len(token2) + 1))

    for t1 in range(len(token1) + 1):
        distances[t1][0] = t1

    for t2 in range(len(token2) + 1):
        distances[0][t2] = t2

    a = 0
    b = 0
    c = 0

    for t1 in range(1, len(token1) + 1):
        for t2 in range(1, len(token2) + 1):
            if (token1[t1-1] == token2[t2-1]):
                distances[t1][t2] = distances[t1 - 1][t2 - 1]
            else:
                a = distances[t1][t2 - 1]
                b = distances[t1 - 1][t2]
                c = distances[t1 - 1][t2 - 1]

                if (a <= b and a <= c):
                    distances[t1][t2] = a + 1
                elif (b <= a and b <= c):
                    distances[t1][t2] = b + 1
                else:
                    distances[t1][t2] = c + 1

    return int(distances[len(token1)][len(token2)])


# logger for errors
def log_error(*args):

    print("\n", datetime.datetime.now())

    for i in args:
        print(i)

    print(traceback.print_exception(*sys.exc_info()))


# logger for messages
def log_message(*args):

    print("\n", datetime.datetime.now())

    for i in args:
        print(i)


# load lists
def load():

    global data_dict

    try:
        with open("data.json") as json_file:
            data_dict = json.load(json_file)

    except FileNotFoundError:
        save()
        load()


# save lists
def save():

    global data_dict

    with open("data.json", "w") as json_file:
        json.dump(data_dict, json_file)


# save current time
def save_time():

    with open("time.txt", "w") as file:
        print(datetime.datetime.now().strftime('%y.%m.%d %H:%M:%S'), file=file)


# load last known time
def load_time():

    try:
        with open("time.txt") as file:
            return datetime.datetime.strptime(file.readline().strip(), '%y.%m.%d %H:%M:%S')

    except FileNotFoundError:
        save_time()
        return load_time()
     

# compare strings
def is_similar(str_1, str_2):

    global similarity

    distance = levenshtein(str(str_1).lower(), str(str_2).lower())

    return 1 - similarity > distance / min(len(str_1), len(str_2))


# check if post was already posted
def is_duplicate(submission, submission_time):

    global data_dict, day_offset

    for title in list(data_dict)[::-1]:
        old_time = datetime.datetime.strptime(data_dict[title]["time"], '%y.%m.%d %H:%M:%S')

        if submission_time - relativedelta(days=day_offset) > old_time:
            del data_dict[title]
            continue

        if is_similar(title, submission.title):
            return True, submission.permalink
    
    return False, None


last_time = load_time()
load()

while True:
    try:
        log_message("Starting subreddits")

        for submission in subreddit.stream.submissions():
            submission_time = datetime.datetime.fromtimestamp(submission.created_utc)

            # only check new posts
            if submission_time > last_time:

                duplicate, link = is_duplicate(submission, submission_time)
                if duplicate:
                    submission.reply("Your post has been removed, because it has been marked as a duplicate of: https://www.reddit.com%s\n\nTo prevent spam, you can only post once per day.\n\nThis action was performed automatically." % link)
                    submission.mod.remove()
                
                else:
                    data_dict[submission.title] = {"time": submission_time.strftime('%y.%m.%d %H:%M:%S'), "link": submission.permalink}
                
                save()
                save_time()

    # An error - sleep and hope it works now
    except:
        log_error("En error occured with subreddits")
        sleep(60)
