"""Analyser

Analyses the data obtained by the crawler following the description of the assignment.
"""
from collections import Counter
from colors import *
import glob
from itertools import chain
import json
import os
import re

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
from operator import itemgetter
from tld import get_fld
from urllib.parse import urlparse


def read_blocklist():
    """Read all domains and their corresponding entities from the blocklist into a set

    Returns
    -------
    dict
        A dictionary with domains of trackers as key and the corresponding entity name as the value
    """
    with open("data/disconnect_blocklist.json", 'rb') as f:
        blocklist = json.load(f)

    # Add every domain in the blocklist to a set
    tracker_domains = dict()

    for cat in blocklist['categories'].keys():
        for item in blocklist['categories'][cat]:
            for entityname, urls in item.items():
                for url, domains in urls.items():
                    if url == "performance":
                        continue
                    for domain in domains:
                        tracker_domains[domain] = entityname
    return tracker_domains


def domain_in_blocklist(tracker_domains, domain):
    """Check whether `domain` is present in the set of tracker domains

    Parameters
    ----------
    tracker_domains: set
        A set of domains that are present in the blocklist
    domain: str
        The domain that needs to be checked

    Returns
    -------
    bool
        A boolean indicating whether the domain is present in the blocklist or not
    """
    if domain in tracker_domains:
        return domain, True

    # Check up to four domains formed by starting with the least five components
    # Following the example of Mozilla's trackingprotection-tools library:
    # (https://github.com/mozilla/trackingprotection-tools/blob/a55109119f0f66ddda92c133cee1d8ee31b64da9/trackingprotection_tools/DisconnectParser.py#L315)
    domain = ".".join(domain.rsplit(".", 5)[1:])
    count = 0
    while domain != "":
        count += 1
        if count > 4:
            return None, False
        if domain in tracker_domains:
            return domain, True
        try:
            domain = domain.split(".", 1)[1]
        except IndexError:
            return None, False
    return None, False


def extract_tracker_domains_entities(third_party_domains, blocklist, blocklist_domains):
    """Extract tracker domains and their corresponding entity name from a list of third-party domains
        using a blocklist

    Parameters
    ----------
    third_party_domains: set
        A set with all distinct third-party domains for a request
    blocklist: dict
        A dictionary with the domains and their corresponding entity names from the blocklist
    blocklist_domains: set
        A set of domains that are present in the blocklist

    Returns
    -------
    tracker_domains: set
        A set of all (distinct) tracker domains for a request
    tracker_entities: set
        A set of all (distinct) tracker entities for a request
    """
    # Store the domains that are present in the blocklist in order to match them with the entity later
    domains = list(filter(None, [domain_in_blocklist(blocklist_domains, d)[0] for d in third_party_domains]))

    # Store the sets with (distinct) tracker domains and their corresponding entities
    tracker_domains = {domain for domain in third_party_domains if domain_in_blocklist(blocklist_domains, domain)[1]}
    tracker_entities = {blocklist[domain] for domain in domains}

    return tracker_domains, tracker_entities


def calculate_page_load_time(start_time, end_time):
    """Calculate the page load time by subtracting the the start_time from end_time

    Parameters
    ----------
    start_time: string
        A string denoting the start time of the pageload
    end_time: string
        A string denoting the end time of the pageload

    Returns
    -------
    float
        The page load time in seconds
    """
    page_load_start = datetime.strptime(start_time, '%d/%m/%Y %H:%M:%S.%f')
    page_load_end = datetime.strptime(end_time, '%d/%m/%Y %H:%M:%S.%f')
    page_load_time = (page_load_end - page_load_start).total_seconds()

    return page_load_time


def write_data_to_dataframe(headers, blocklist, blocklist_domains):
    """Writes the data from the JSON files for all the crawled websites to a CSV file

    Parameters
    ----------
    headers: list
        A list with the values for the headers of the data in the JSON files
    blocklist: dict
        A dictionary with domains of trackers as key and the corresponding entity name as the value
    blocklist_domains: set
        A list of domains that are in the blocklist

    Returns
    -------
    dataframe: pandas.core.frame.DataFrame
        A Pandas dataframe with all the data that needs to be analysed
    err_dataframe: pandas.core.frame.DataFrame
        A Pandas dataframe containing all domains where errors occured
    """
    data = []
    errors = []

    # Get all JSON files within the crawl_data folder
    files = glob.glob("../crawl_data/*.json")
    for file in files:
        with open(file, 'r') as f:
            try:
                json_file = json.load(f)
                # If an error occured, only 4 items will be stored in the json file
                if len(json_file) == 4:
                    errors.append([json_file['website_domain'],
                                   json_file['tranco_rank'],
                                   json_file['crawl_mode'],
                                   json_file['error']])
                else:
                    tracker_domains, tracker_entities = extract_tracker_domains_entities(
                        json_file['third_party_domains'], blocklist, blocklist_domains)
                    page_load_time = calculate_page_load_time(json_file['pageload_start_ts'], json_file['pageload_end_ts'])
                    data.append([json_file['website_domain'],
                                 json_file['tranco_rank'],
                                 json_file['crawl_mode'],
                                 json_file['pageload_start_ts'],
                                 json_file['pageload_end_ts'],
                                 page_load_time,
                                 json_file['post_pageload_url'],
                                 json_file['consent_status'],
                                 json_file['cookies'],
                                 json_file['third_party_domains'],
                                 len(json_file['third_party_domains']),
                                 json_file['requests'],
                                 len(json_file['requests']),
                                 list(tracker_domains),
                                 len(tracker_domains),
                                 list(tracker_entities),
                                 len(tracker_entities),
                                 json_file['redirect_pairs']])
            except KeyError:
                print(f"Skipping {file} because of bad formatting.")

    # Write the data to a Pandas dataframe
    dataframe = pd.DataFrame(data, columns=headers)
    err_dataframe = pd.DataFrame(errors, columns=["website_domain", "tranco_rank", "crawl_mode", "error"])

    return dataframe, err_dataframe


def preprocess_data():
    """This function turns the data into a csv file and in turn this csv file to a Pandas dataframe

    Returns
    -------
    dataframe: pandas.core.frame.DataFrame
        A Pandas dataframe with all the data that needs to be analysed
    err_dataframe: pandas.core.frame.DataFrame
        A Pandas dataframe containing all domains where errors occured
    """
    headers = ["website_domain", "tranco_rank", "crawl_mode", "pageload_start_ts", "pageload_end_ts", "page_load_time",
               "post_pageload_url", "consent_status", "cookies", "third_party_domains", "nr_third_party_domains",
               "requests", "nr_requests", "tracker_domains", "nr_tracker_domains", "tracker_entities",
               "nr_tracker_entities", "redirection_pairs"]
    blocklist = read_blocklist()
    blocklist_domains = set(blocklist.keys())

    dataframe, err_dataframe = write_data_to_dataframe(headers, blocklist, blocklist_domains)

    return dataframe, err_dataframe, blocklist_domains


def generate_entry_table_question_1(header):
    """Generate a header specific entry for the table on the number of failures encountered during each crawl

    Parameters
    ----------
    header: tuple
        A tuple holding the header name and value that need to be filtered, the belonging text that should appear
            in the entry and the dataframe that the data should be filtered from

    Returns
    -------
    string
        A string that holds the precise entry text that will be added in the table
    """
    target, val, text, df = header
    err_desktop = df[(df['crawl_mode'] == "Desktop") & (df[target] == val)]
    err_mobile = df[(df['crawl_mode'] == "Mobile") & (df[target] == val)]

    entry = "%s & %s & %s \\\\ \hline \n" % (text, len(err_desktop), len(err_mobile))

    return entry


def generate_table_question_1(dataframe, err_dataframe):
    """Generate a LaTeX table on the number of failures encountered during each crawl

    Parameters
    ----------
    dataframe: pandas.core.frame.DataFrame
        A Pandas dataframe with all the data that needs to be analysed
    err_dataframe: pandas.core.frame.DataFrame
        A Pandas dataframe containing all domains where errors occured
    """
    # # A list of tuples holding the error and text that should appear in the table for that error
    headers = [("error", "Timeout", "Page load timeout", err_dataframe), ("error", "TLS", "TLS error", err_dataframe),
               ("consent_status", "errored", "Consent click error", dataframe)]

    # Remove the file if it is already existing
    if os.path.isfile("data/table_question_1.tex"):
        os.remove("data/table_question_1.tex")

    # Open the file and write to it
    file = open("data/table_question_1.tex", "a")
    file.write("\\begin{table}[ht] \n")
    file.write("\caption{Number of failures encountered during each crawl.} \n")
    file.write("\centering \n")
    file.write("\\begin{tabular}{|l|r|r|} \n")
    file.write("\hline \n")
    file.write(
        "\\textbf{Error type} & \multicolumn{1}{l|}{\\textbf{Crawl-desktop}} & \multicolumn{1}{l|}{\\textbf{Crawl-mobile}} \\\\ \hline \n")

    for header in headers:
        entry = generate_entry_table_question_1(header)
        file.write(entry)

    file.write("\end{tabular} \n")
    file.write("\label{table:NumberOfFailures} \n")
    file.write("\end{table}")

    # Close the file
    file.close()


def customize_grid(ax, border, yaxis, xaxis, bg_color='white', grid_color='gray', width=1.2, yminor=True, xminor=True):
    """Customize the looks of the grid

    Parameters
    ----------
    ax: matplotlib.axes._subplots.AxesSubplot
        The matplotlib axes instance the plot is drawn on
    border: bool
        A Boolean value that defines whether or not the border needs to be drawn
    yaxis, xaxis: bool
        Boolean values that define whether respectively the horizontal and vertical
         (mayor) grid lines need to be drawn
    bg_color: str, default='white'
        The background color of the grid
    grid_color: str, default='gray'
        The color of the grid lines
    width: float, default=1.2
        The width of the grid lines
    yminor, xminor: bool, default=True
       Boolean values that define whether respectively the horizontal and vertical
        minor grid lines need to be drawn
    """
    ax.set_facecolor(bg_color)  # Set background color
    [ax.spines[spine].set_visible(border) for spine in ax.spines]  # Remove border around the grid
    if yaxis:
        ax.yaxis.grid(yaxis, which='major', color=grid_color, linewidth=width)
    if yminor:
        ax.yaxis.grid(yminor, which='minor', color=grid_color, linewidth=width / 4)
    if xaxis:
        ax.xaxis.grid(xaxis, which='major', color=grid_color, linewidth=width)
    if xminor:
        ax.xaxis.grid(xminor, which='minor', color=grid_color, linewidth=width / 4)
    if yminor or xminor:  # Show minor grid lines, but not minor ticks
        ax.minorticks_on()
        ax.tick_params(which='minor', bottom=False, left=False)
    ax.set(axisbelow=True)  # Do not draw the grid over the plotted items


def customize_box_plot_color(ax):
    """Customize the colors of all boxplot parts

    Parameters
    ----------
    ax: matplotlib.axes._subplots.AxesSubplot
        The matplotlib axes instance the plot is drawn on
    """
    for i, box in enumerate(ax['boxes']):
        box.set(facecolor=BOX_FACECOLOR[i], edgecolor=BOX_EDGECOLOR[i])
    for whisker in ax['whiskers']:
        whisker.set(color=BOX_LINE, linestyle=':')
    for cap in ax['caps']:
        cap.set_color(BOX_LINE)
    for median in ax['medians']:
        median.set(color=BOX_MEDIAN)
    for flier in ax['fliers']:
        flier.set(color=BOX_EDGECOLOR[i], marker='o')


def generate_box_plot(dataframe, header, crawl_mode, metric):
    """Generate a box plot for dataframe[header] grouped by crawl_mode

    Parameters
    ----------
    dataframe: pandas.core.frame.DataFrame
        A Pandas dataframe with all the data that needs to be analysed
    header: string
        A string with the value for one of the headers of the data in the dataframe
    crawl_mode: string
        A string with the value for the crawl_mode header of the data in the dataframe
    metric: string
        A string with the metric that is plotted
    """
    bp_dict = dataframe.boxplot(header, grid=False, by=crawl_mode, return_type='both', patch_artist=True)
    customize_grid(bp_dict[0][0], False, True, False, BOX_BACKGROUND, BOX_GRID, xminor=False)
    customize_box_plot_color(bp_dict[0][1])
    plt.title(f"The distribution of the {metric} per website\nfor both desktop and mobile crawl mode.")
    plt.suptitle("")  # Remove the automatic "grouped by" title
    plt.xlabel("Crawl mode")
    plt.ylabel(metric.capitalize())
    plt.savefig(f"data/box_plot_{header}.png", bbox_inches='tight')
    # plt.show()
    plt.close()


def generate_box_plots_question_2(dataframe):
    """Generate five box plots to compare the data from the two crawls

    Parameters
    ----------
    dataframe: pandas.core.frame.DataFrame
        A Pandas dataframe with all the data that needs to be analysed
    """
    generate_box_plot(dataframe, "page_load_time", "crawl_mode", "page load time")
    generate_box_plot(dataframe, "nr_requests", "crawl_mode", "number of requests")
    generate_box_plot(dataframe, "nr_third_party_domains", "crawl_mode", "number of disctinct third-party domains")
    generate_box_plot(dataframe, "nr_tracker_domains", "crawl_mode", "number of disctinct tracker domains")
    generate_box_plot(dataframe, "nr_tracker_entities", "crawl_mode", "number of disctinct tracker entities")


def generate_entry_table_question_3(dataframe, header):
    """Generate a header specific entry for the table about the comparison of desktop and mobile crawl data

    Parameters
    ----------
    dataframe: pandas.core.frame.DataFrame
        A Pandas dataframe with all the data that needs to be analysed
    header: tuple
        A tuple holding the header name and belonging text that should appear in the entry

    Returns
    -------
    string
        A string that holds the precise entry text that will be added in the table
    """
    # Sort the CSV data by crawl_mode and then by the value of the provided header
    df = dataframe.sort_values(['crawl_mode', header[0]]).groupby('crawl_mode')

    # Get the minimum, maximum and median values for each provided header
    min_desktop = df[header[0]].min()[0]
    max_desktop = df[header[0]].max()[0]
    median_desktop = df[header[0]].median()[0]
    min_mobile = df[header[0]].min()[1]
    max_mobile = df[header[0]].max()[1]
    median_mobile = df[header[0]].median()[1]

    entry = "%s & \multicolumn{1}{r|}{%s} & \multicolumn{1}{r|}{%s} & \multicolumn{1}{r|}{%s} & \multicolumn{1}{r|}{%s} & \multicolumn{1}{r|}{%s} & \multicolumn{1}{r|}{%s} \\\\ \hline \n" % (
        header[1], min_desktop, max_desktop, median_desktop, min_mobile, max_mobile, median_mobile)

    return entry


def generate_table_question_3(dataframe):
    """Generate a LaTeX table about the comparison of desktop and mobile crawl data in a file

    Parameters
    ----------
    dataframe: pandas.core.frame.DataFrame
        A Pandas dataframe with all the data that needs to be analysed
    """
    # A list of tuples holding the headers and text that should appear in the table
    headers = [("page_load_time", "Page load time(s)"), ("nr_requests", "\# requests"),
               ("nr_third_party_domains", "\# distinct third parties"),
               ("nr_tracker_domains", "\# distinct tracker domains"),
               ("nr_tracker_entities", "\# distinct tracker entities/companies")]

    # Remove the file if it is already existing
    if os.path.isfile("data/table_question_3.tex"):
        os.remove("data/table_question_3.tex")

    # Open the file and write to it
    file = open("data/table_question_3.tex", "a")
    file.write("\\begin{table}[ht] \n")
    file.write("\caption{Comparison of the desktop and mobile crawl data.} \n")
    file.write("\centering \n")
    file.write("\\begin{tabular}{|l|rrl|lll|} \n")
    file.write("\\hline \n")
    file.write(
        "\\textbf{} & \multicolumn{3}{c|}{\\textbf{Crawl-desktop}} & \multicolumn{3}{c|}{\\textbf{Crawl-mobile}} \\\\ \hline \n")
    file.write(
        "\\textbf{Metric} & \multicolumn{1}{r|}{\\textbf{Min}} & \multicolumn{1}{r|}{\\textbf{Max}} & \\textbf{Median} & \multicolumn{1}{l|}{\\textbf{Min}} & \multicolumn{1}{l|}{\\textbf{Max}} & \\textbf{Median} \\\\ \hline \n")

    for header in headers:
        entry = generate_entry_table_question_3(dataframe, header)
        file.write(entry)

    file.write("\end{tabular} \n")
    file.write("\label{table:Comparison} \n")
    file.write("\end{table}")

    # Close the file
    file.close()


def prevalence(dataframe, mode, target):
    """Find the prevalence of the targeted group in the crawl

    Parameters
    ----------
    dataframe: pandas.core.frame.DataFrame
        A Pandas dataframe with all the data that needs to be analysed
    mode: string
        A string that holds the crawl-mode to use: either desktop or mobile
    target: string
        The group that the prevalence needs to be found for, e.g., third-party domains

    Returns
    -------
    collections.Counter
        A counter object, holding a dictionary of all items of the targeted group (as keys)
        and their prevalence (as values) in the crawl
    """
    # Collect all items belonging to the target group for the (desktop or mobile) crawl
    third_parties = dataframe.loc[dataframe["crawl_mode"] == mode, target]
    # Turn the pandas series into a list and flatten it
    third_parties_list = list(chain.from_iterable(third_parties))
    # Use Python Counter to return the count of every element in the list
    counter_third_parties = Counter(third_parties_list)

    return counter_third_parties


def generate_table_question(questionnr, target, top_ten_desktop, top_ten_mobile, label=""):
    """Generate a LaTeX table for questions 4, 5 and 6

    Parameters
    ----------
    questionnr: int
        The number of the question for which the table needs to be generated
    target: str
        The target that we are building the prevalence table for, e.g., third-party domains
    top_ten_desktop: list
        The top ten prevalent instances of the target for the desktop crawl mode
    top_ten_mobile: list
        The top ten prevalent instances of the target for the mobile crawl mode
    """
    # Remove the file if it is already existing
    if os.path.isfile(f"data/table_question_{questionnr}.tex"):
        os.remove(f"data/table_question_{questionnr}.tex")

    # Open the file and write to it
    file = open(f"data/table_question_{questionnr}.tex", 'a')
    file.write("\\begin{table}[ht] \n")
    file.write("\caption{The ten most prevalent %ss for each crawl.} \n" % (re.sub(r'y$', r'ie', target)))
    file.write("\centering \n")
    file.write("\\begin{tabular}{|l|ll|ll|} \n")
    file.write("\hline")
    file.write(
        "\\textbf{} & \multicolumn{2}{c|}{\\textbf{Crawl-desktop}} & " +
        "\multicolumn{2}{c|}{\\textbf{Crawl-mobile}} \\\\ \hline \n")
    file.write(
        "& \multicolumn{1}{r|}{\\textbf{%s}} & \\textbf{\# websites} & " % (target.capitalize()) +
        "\multicolumn{1}{l|}{\\textbf{%s}} & \\textbf{\# websites} \\\\ \hline \n" % (target.capitalize()))

    # Write the data of the top ten for both mobile and desktop to the table
    for i in range(10):
        entry = ("\\textbf{%d} & \multicolumn{1}{l|}{%s} & " % (i + 1, top_ten_desktop[i][0]) +
                 "\multicolumn{1}{r|}{%d} & \multicolumn{1}{l|}{%s} & " % (
                     top_ten_desktop[i][1], top_ten_mobile[i][0]) +
                 "\multicolumn{1}{r|}{%d} \\\\ \hline \n" % (top_ten_mobile[i][1]))
        file.write(entry)

    file.write("\end{tabular} \n")
    file.write("\label{tab:%sTop10} \n" % (re.sub(r'(Third-Party|Domain| )', '', target.title())))
    file.write("\end{table}")

    # Close the file
    file.close()


def generate_table_question_4(dataframe):
    """Generate a LaTeX table holding the ten most prevalent third-party domains for each crawl

    Parameters
    ----------
    dataframe: pandas.core.frame.DataFrame
        A Pandas dataframe with all the data that needs to be analysed
    """
    top_ten_desktop = prevalence(dataframe, "Desktop", "third_party_domains").most_common(10)
    top_ten_mobile = prevalence(dataframe, "Mobile", "third_party_domains").most_common(10)

    generate_table_question(4, "third-party domain", top_ten_desktop, top_ten_mobile)


def generate_table_question_5(dataframe):
    """Generate a LaTeX table holding the ten most prevalent third-party tracker domains for each crawl

    Parameters
    ----------
    dataframe: pandas.core.frame.DataFrame
        A Pandas dataframe with all the data that needs to be analysed
    """
    top_ten_tracker_desktop = prevalence(dataframe, "Desktop", "tracker_domains").most_common(10)
    top_ten_tracker_mobile = prevalence(dataframe, "Mobile", "tracker_domains").most_common(10)

    generate_table_question(5, "tracker domain", top_ten_tracker_desktop, top_ten_tracker_mobile)


def generate_table_question_6(dataframe):
    """Generate a LaTeX table holding the ten most prevalent tracker entities (companies) for each crawl

    Parameters
    ----------
    dataframe: pandas.core.frame.DataFrame
        A Pandas dataframe with all the data that needs to be analysed
    """
    top_ten_entities_desktop = prevalence(dataframe, "Desktop", "tracker_entities").most_common(10)
    top_ten_entities_mobile = prevalence(dataframe, "Mobile", "tracker_entities").most_common(10)
    generate_table_question(6, "tracker entity", top_ten_entities_desktop, top_ten_entities_mobile)


def generate_scatter_plot(dataframe, mode, png_text, plot_text, target):
    """Generate scatter plots of the provided data along with a linear regression line

    Parameters
    ----------
    dataframe: pandas.core.frame.DataFrame
        A Pandas dataframe with all the data that needs to be analysed
    mode: string
        A string that holds the crawl-mode to use: either desktop or mobile
    png_text: string
        A string that holds information on how to name the output .png file
    plot_text: string
        A string that holds information on how to name the text on the y-axis
    target: string
        The group that the scatter plot needs to plot
    """
    # Make a dataframe with the columns tranco rank and number of third party domains filtered on crawl mode
    df = dataframe.loc[dataframe["crawl_mode"] == mode, ["tranco_rank", target]].rename(
        columns={"tranco_rank": "Website's Tranco rank", target: plot_text})

    # Make the scatter plot
    sns.lmplot(x="Website's Tranco rank", y=plot_text, data=df)
    plt.title(f"The {plot_text.lower()} vs the website's Tranco rank ({mode}-crawl)")
    plt.savefig(f"data/scatter_plot_{png_text}_{mode}.png", bbox_inches='tight')
    # plt.show()  # use plt.show(block=True) if the window closes too soon
    plt.close()


def generate_scatter_plots_question_7(dataframe):
    """Generate the scatter plots showing the number of distinct third parties vs the website's Tranco rank

    Parameters
    ----------
    dataframe: pandas.core.frame.DataFrame
        A Pandas dataframe with all the data that needs to be analysed
    """
    generate_scatter_plot(dataframe, "Desktop", "third_parties", "Number of distinct third parties", "nr_third_party_domains")
    generate_scatter_plot(dataframe, "Mobile", "third_parties", "Number of distinct third parties", "nr_third_party_domains")


def generate_scatter_plots_question_8(dataframe):
    """Generate the scatter plots showing the number of distinct trackers vs the website's Tranco rank

    Parameters
    ----------
    dataframe: pandas.core.frame.DataFrame
        A Pandas dataframe with all the data that needs to be analysed
    """
    generate_scatter_plot(dataframe, "Desktop", "trackers", "Number of distinct trackers", "nr_tracker_domains")
    generate_scatter_plot(dataframe, "Mobile", "trackers", "Number of distinct trackers", "nr_tracker_domains")


def find_request_with_most_cookies(dataframe, mode):
    """Find the request (and website domain) with the most number of cookies

    Parameters
    ----------
    dataframe: pandas.core.frame.DataFrame
        A Pandas dataframe with all the data that needs to be analysed
    mode: string
        A string that holds the crawl-mode to use: either desktop or mobile

    Returns
    -------
    request_hostname: string
        A string holding the hostname of the request
    website: string
        A string holding the website domain belonging to the request
    most_number_of_cookies: int
        An integer holding the number of cookies set by the request
    """
    # reset_index(drop=True) resets the indices from 0 to the length of the number of entries in the
    # dataframe that correspond to the right crawl mode
    requests = dataframe.loc[dataframe["crawl_mode"] == mode, "requests"].reset_index(drop=True)
    website_domain = dataframe.loc[dataframe["crawl_mode"] == mode, "website_domain"].reset_index(drop=True)
    most_number_of_cookies = 0
    request_hostname = ""
    website = ""

    # Search through all requests in the requests_list for the most cookies
    for i, requests_domain in enumerate(requests):
        for request in requests_domain:
            request_url = request.get("request_url")
            nr_cookies = request.get("nr_cookies")
            if most_number_of_cookies < nr_cookies:
                most_number_of_cookies = nr_cookies
                request_hostname = urlparse(request_url).hostname
                website = website_domain[i]

    return request_hostname, website, most_number_of_cookies


def generate_entry_table_question_9(dataframe, mode):
    """Generate a header specific entry for the table about the request with the most cookies

    Parameters
    ----------
    dataframe: pandas.core.frame.DataFrame
        A Pandas dataframe with all the data that needs to be analysed
    mode: string
        A string that holds the crawl-mode to use: either desktop or mobile

    Returns
    -------
    string
        A string that holds the precise entry text that will be added in the table
    """
    request_hostname, website, most_number_of_cookies = find_request_with_most_cookies(dataframe, mode)

    # Check if the request hostname matches the website domain and set first_party accordingly
    if get_fld(request_hostname, fix_protocol=True) == website:
        first_party = "Yes"
    else:
        first_party = "No"

    entry = "\\textbf{%s} & %s & %s & %s & %s \\\\ \hline \n" % (mode, request_hostname, website, most_number_of_cookies, first_party)

    return entry


def generate_table_question_9(dataframe):
    """Generate a LaTeX table holding the request with the most cookies for each crawl

    Parameters
    ----------
    dataframe: pandas.core.frame.DataFrame
        A Pandas dataframe with all the data that needs to be analysed
    """
    # Remove the file if it is already existing
    if os.path.isfile(f"data/table_question_9.tex"):
        os.remove(f"data/table_question_9.tex")

    # Open the file and write to it
    file = open(f"data/table_question_9.tex", 'a')
    file.write("\\begin{table}[ht] \n")
    file.write("\caption{Request with the most cookies for the desktop and mobile crawl.} \n")
    file.write("\centering \n")
    file.write("\\begin{tabular}{|l|l|l|r|c|} \n")
    file.write("\hline")
    file.write(
        "\\textbf{Crawl} & \\textbf{Request hostname} & \\textbf{Website} & " +
        "\multicolumn{1}{l|}{\\textbf{\# cookies}} & \multicolumn{1}{l|}{\\textbf{First-party request}} \\\\ \hline \n")

    # Write the data for the request with the most cookies to the file
    entry_desktop = generate_entry_table_question_9(dataframe, "Desktop")
    file.write(entry_desktop)
    entry_mobile = generate_entry_table_question_9(dataframe, "Mobile")
    file.write(entry_mobile)

    file.write("\end{tabular} \n")
    file.write("\label{tab:mostcookies} \n")
    file.write("\end{table}")

    # Close the file
    file.close()


def find_cookies_longest_lifespans(dataframe, mode, number):
    """Find the three cookies with the longest lifespans

    Parameters
    ----------
    dataframe: pandas.core.frame.DataFrame
        A Pandas dataframe with all the data that needs to be analysed
    mode: string
        A string that holds the crawl-mode to use: either desktop or mobile
    number: int
        An integer holding the value of whether we want the first, second or third cookie regarding the lifespans

    Returns
    -------
    longest_lifespans_cookies: dict
        A dictionary holding the three cookies with the longest lifespans
    longest_lifespans[number][1]: string
        A string holding the information whether the maximal life span was in the Max-Age or Expires column
    """
    # reset_index(drop=True) resets the indices from 0 to the length of the number of entries in the
    # dataframe that correspond to the right crawl mode
    cookies_list = dataframe.loc[dataframe["crawl_mode"] == mode, "cookies"].reset_index(drop=True)
    lifespans = []

    for i, entry_with_cookie_dicts in enumerate(cookies_list):
        if entry_with_cookie_dicts:
            for j, cookie_dict in enumerate(entry_with_cookie_dicts):
                max_age = cookie_dict.get("Max-Age")
                expiry = cookie_dict.get("Expires")
                # max_age overrides the expires field: https://www.rfc-editor.org/rfc/rfc7234#section-5.3
                if max_age:
                    lifespans.append([float(max_age), "max-age", i, j])
                elif expiry and expiry != "Session":
                    # Change the dates to in how many seconds they will expire
                    expiry = expiry.replace("-", "").replace(" ", "")
                    # In case the day name is written in full, then only take the first 3 letters
                    if len(expiry) >= 24:
                        day, rest = expiry.split(",")
                        expiry = day[:3] + "," + rest
                    # Remove if there is a timezone or trailing zeros
                    if (len(expiry) == 21 or len(expiry) == 22 or len(expiry) == 23 or len(expiry) == 24) and \
                            ":" not in expiry[-4:]:
                        expiry = expiry[:-4]
                    # Exception for when the year is only 2 digits
                    try:
                        expiry = datetime.strptime(expiry, '%a,%d%b%Y%H:%M:%S')
                        current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        current_time = datetime.strptime(current_time_str, '%Y-%m-%d %H:%M:%S')
                    except ValueError:
                        expiry = datetime.strptime(expiry, '%a,%d%b%y%H:%M:%S')
                        current_time_str = datetime.now().strftime("%y-%m-%d %H:%M:%S")
                        current_time = datetime.strptime(current_time_str, '%y-%m-%d %H:%M:%S')
                    expiry_age = (expiry - current_time).total_seconds()
                    lifespans.append([expiry_age, "expires", i, j])

    # Sort the list of lists on the first argument of the inner list
    longest_lifespans = sorted(lifespans, key=itemgetter(0), reverse=True)[:3]
    longest_lifespans_cookies = cookies_list[longest_lifespans[number][2]][longest_lifespans[number][3]]

    return longest_lifespans_cookies, longest_lifespans[number][1]


def replace_dict_value(dictionary, key, value):
    """Replace possible None values to self-defined values

    Parameters
    ----------
    dictionary: dict
        A dictionary holding the three cookies with the longest lifespans
    key: string
        The key we want to use in the get-function in order to get the belonging value
    value: string
        If the get-function returns None, we want to have "value" instead

    Returns
    -------
    string
        Either the value that returned from the get-function or the value given as parameter
    """
    dictionary_output = dictionary.get(key)

    if dictionary_output:
        official_value = dictionary_output
    else:
        official_value = value

    return official_value


def generate_entry_table_question_10(longest_lifespans_cookies, column):
    """Generate a header specific entry for the table about the cookies with the longest lifespan

    Parameters
    ----------
    longest_lifespans_cookies: dict
        A dictionary holding the three cookies with the longest lifespans
    column: string
        A string holding the information whether the maximal life span was in the Max-Age or Expires column

    Returns
    -------
    string
        A string that holds the precise entry text that will be added in the table
    """
    # First cast the dictionary keys to lowercase and then build up the table entry
    cookie_dict = {k.lower(): v for k, v in longest_lifespans_cookies.items()}
    name = list(longest_lifespans_cookies.keys())[0]
    value = cookie_dict.get(name.lower())
    domain = replace_dict_value(cookie_dict, "domain", "-")
    path = replace_dict_value(cookie_dict, "path", "-")
    expiry = cookie_dict.get(column)
    size = len(value)
    httponly = replace_dict_value(cookie_dict, "httponly", "False")
    secure = replace_dict_value(cookie_dict, "secure", "False")
    samesite = cookie_dict.get("samesite")

    entry = "%s & %s & %s & %s & %s & %s & %s & %s & %s \\\\ \hline \n" % (name, value, domain, path, expiry, size,
                                                                        httponly, secure, samesite)

    return entry


def generate_table_question_10(dataframe, mode):
    """Generate a LaTeX table holding the three cookies with the longest lifespan in the `crawl_mode` crawl

    Parameters
    ----------
    dataframe: pandas.core.frame.DataFrame
        A Pandas dataframe with all the data that needs to be analysed
    mode: str
        The crawl mode for which the table needs to be generated
    """
    # Remove the file if it is already existing
    if os.path.isfile(f"data/table_question_10_{mode.lower()}.tex"):
        os.remove(f"data/table_question_10_{mode.lower()}.tex")

    # Open the file and write to it
    file = open(f"data/table_question_10_{mode.lower()}.tex", 'a')
    file.write("\\begin{table}[!htbp] \n")
    file.write("\caption{Three cookies with the longest lifespan in the %s crawl.} \n" % mode)
    file.write("\centering \n")
    file.write("\\resizebox{\\textwidth}{!}{\\begin{tabular}{|l|l|l|l|l|l|l|l|l|} \n")
    file.write("\hline\\rowcolor{lightgray} \n")
    file.write(
        "\\textbf{Name} & \\textbf{Value} & \\textbf{Domain} & \\textbf{Path} & \\textbf{Expires / Max-Age} & " +
        "\\textbf{Size} & \\textbf{HttpOnly} & \\textbf{Secure} & \\textbf{SameSite} \\\\ \hline \n")

    # Write the data for the three cookies with the longest expiry
    for i in range(3):
        longest_lifespans_cookies, column = find_cookies_longest_lifespans(dataframe, mode, i)
        entry = generate_entry_table_question_10(longest_lifespans_cookies, column)
        file.write(entry)

    file.write("\end{tabular}} \n")
    file.write("\label{tab:lifespan_%s} \n" % mode)
    file.write("\end{table}")

    # Close the file
    file.close()


def top_ten_tracker_redirection_pairs(dataframe, mode, tracker_domains):
    """Generate a list holding the ten most prevalent cross-domain HTTP redirection pairs for the `mode` crawl

    Parameters
    ----------
    dataframe: pandas.core.frame.DataFrame
        A Pandas dataframe with all the data that needs to be analysed
    mode: str
        The crawl mode for which the list needs to be generated
    tracker_domains: set
        A set of all (distinct) tracker domains in the blocklist

    Returns:
    --------
    list
        A list with the top ten prevalent cross-domain HTTP redirection pairs
    """
    # Filter the redirection pairs for the crawl mode
    pairs = dataframe.loc[dataframe["crawl_mode"] == mode, "redirection_pairs"]
    # Get all tuples of redirection pairs into a list of tuples
    pairs_tuples = [tuple(i) for i in list(chain.from_iterable(pairs))]
    # Filter the redirection pairs that involve a tracker domain and get the top ten most prevalent pairs
    tracker_pairs = [p for p in pairs_tuples if domain_in_blocklist(tracker_domains, p[0])[1] or domain_in_blocklist(tracker_domains, p[1])[1]]
    top_ten_pairs = Counter(tracker_pairs).most_common(10)

    return top_ten_pairs


def generate_table_question_11(crawl_mode, top_ten_redirection_pairs):
    """Generate a LaTeX table holding the ten most prevalent cross-domain HTTP redirection pairs for the `crawl_mode` crawl

    Parameters
    ----------
    crawl_mode: str
        The crawl mode for which the table needs to be generated
    top_ten_redirection_pairs: list
        A list with the top ten prevalent cross-domain HTTP redirection pairs
    """
    # Remove the file if it is already existing
    if os.path.isfile(f"data/table_question_11_{crawl_mode.lower()}.tex"):
        os.remove(f"data/table_question_11_{crawl_mode.lower()}.tex")

    # Open the file and write to it
    file = open(f"data/table_question_11_{crawl_mode.lower()}.tex", 'a')
    file.write("\\begin{table}[ht] \n")
    file.write("\caption{The ten most prevalent cross-domain HTTP redirection pairs (%s crawl).} \n" % (crawl_mode))
    file.write("\centering \n")
    file.write("\\begin{tabular}{|l|l|l|l|} \n")
    file.write("\hline \n")
    file.write(
        "& \\textbf{Source hostname} & \\textbf{Target hostname} & \\textbf{Number of distinct websites} \\\\ \hline \n")

    # Write the data of the top ten redirection pairs for both mobile and desktop to the table
    for i in range(10):
        entry = ("\\textbf{%d} & %s & %s & " % (i + 1, top_ten_redirection_pairs[i][0][0], top_ten_redirection_pairs[i][0][1]) +
                 "\multicolumn{1}{r|}{%d} \\\\ \hline \n" % (top_ten_redirection_pairs[i][1]))
        file.write(entry)

    file.write("\end{tabular} \n")
    file.write("\label{tab:redirections%s} \n" % (crawl_mode))
    file.write("\end{table}")

    # Close the file
    file.close()


def generate_tables_question_11(dataframe, tracker_domains):
    """Generate a LaTeX table holding the ten most prevalent third-party domains for each crawl

    Parameters
    ----------
    dataframe: pandas.core.frame.DataFrame
        A Pandas dataframe with all the data that needs to be analysed
    tracker_domains: set
        A set of all (distinct) tracker domains in the blocklist
    """
    top_ten_desktop = top_ten_tracker_redirection_pairs(dataframe, "Desktop", tracker_domains)
    top_ten_mobile = top_ten_tracker_redirection_pairs(dataframe, "Mobile", tracker_domains)

    generate_table_question_11("Desktop", top_ten_desktop)
    generate_table_question_11("Mobile", top_ten_mobile)


def main():
    # We first preprocess the data and turn it into a Pandas dataframe
    dataframe, err_dataframe, tracker_domains = preprocess_data()

    # Generate answers for all the questions in the assignment
    generate_table_question_1(dataframe, err_dataframe)
    generate_box_plots_question_2(dataframe)
    generate_table_question_3(dataframe)
    generate_table_question_4(dataframe)
    generate_table_question_5(dataframe)
    generate_table_question_6(dataframe)
    generate_scatter_plots_question_7(dataframe)
    generate_scatter_plots_question_8(dataframe)
    generate_table_question_9(dataframe)
    generate_table_question_10(dataframe, "Desktop")
    generate_table_question_10(dataframe, "Mobile")
    generate_tables_question_11(dataframe, tracker_domains)


if __name__ == '__main__':
    # Set theme that seaborn should use
    sns.set_theme(color_codes=True)

    # Change the current working directory to the directory of the running file:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    # Start main function
    main()
