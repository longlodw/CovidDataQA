#! /usr/bin/python3
import re
import gspread
import sys
import csv
import getopt
import os
from urllib.request import urlopen, Request

def downloadURL(url, path):
    with open(path, "w") as file:
        file.write(urlopen(Request(url, headers={'User-Agent': 'Mozilla/5.0'})).read().decode("utf-8"))

def downloadGoogleSheet(url, path, authen_file_path):
    account = gspread.service_account(filename=authen_file_path)
    sheet = account.open(url).get_worksheet(0)
    result = ""
    for e in sheet.get_all_values():
        for i in e:
            result = result + removeLocationType(re.sub(", .*", "", i).replace(",", "")) + ","
        result = result + "\n"
    with open(path, "w") as file:
        file.write(result)

def openCSVAsList(path):
    with open(path, "r") as file:
        return list(csv.reader(file))

def find(data, pattern, count = None):
    result = []
    for r, row in enumerate(data):
        for c, e in enumerate(row):
            if re.match(pattern, e):
                result.append((r, c))
                if count != None:
                    count-=1
                    if count <= 0:
                        return result
    return result

def removeLocationType(string):
    string = string.replace("City and Borough").replace("County", " ").replace("Borough", " ").replace("Census Area", " ").replace("Municipality", " ").replace("Municipio", " ").replace("Parish", " ")
    return re.sub("  +", "", re.sub("Consolidated .* of", " ", string))

def getBrstr(fips, year, month, day, path):
    result = {}
    data = openCSVAsList(path)
    fips_col = 1
    county_col = 3
    date_cols = find(data, month + "/" + day + "/" + year, count=1)
    if len(date_cols) < 1:
        return None
    date_col = date_cols[0][1]
    fips_pattern = "^"
    for e in fips:
        fips_pattern = fips_pattern + e + "{" + "1}"
    fips_pattern = fips_pattern + "$"
    counties = find(data, fips_pattern)
    for e in counties:
        if e[1] == fips_col:
            county = data[e[0]][county_col]
            if re.match(".*state.*", county):
                result["state total"] = (int(data[e[0]][date_col]), int(data[e[0]][date_col + 2]))
            elif county != "Unknown":
                result[county] = (int(data[e[0]][date_col]) + int(data[e[0]][date_col + 1]), int(data[e[0]][date_col + 2]) + int(data[e[0]][date_col + 3]))
    return result

def getJHU(fips, year, month, day, case_path, death_path):
    result = {}
    case_data = openCSVAsList(case_path)
    death_data = openCSVAsList(death_path)
    fips_col = 4
    county_col = 5
    date = month + "/" + day + "/" + str(int(year) % 100)
    case_date_cols = find(case_data, date, count = 1)
    death_date_cols = find(death_data, date, count = 1)
    if len(case_date_cols) < 1 or len(death_date_cols) < 1:
        return None
    case_date_col = case_date_cols[0][1]
    death_date_col = death_date_cols[0][1]
    case_counties = find(case_data, fips + "...\.0")
    #death_counties = find(death_data, fips + ".0")
    case_total = 0
    death_total = 0
    for e in case_counties:
        if e[1] == fips_col:
            county = case_data[e[0]][county_col]
            case_total += int(case_data[e[0]][case_date_col])
            death_total += int(death_data[e[0]][death_date_col])
            if county != "Unassigned":
                result[county] = (int(case_data[e[0]][case_date_col]), int(death_data[e[0]][death_date_col]))
    result["state total"] = (case_total, death_total)
    return result

def getNYT(fips, year, month, day, path):
    result = {}
    data = openCSVAsList(path)
    fips_col = 3
    county_col = 1
    case_total = 0
    death_total = 0
    date = year + "-" + (month if len(month) == 2 else ("0" + month)) + "-" + (day if len(day) == 2 else ("0" + day))
    data_dates = find(data, date)
    for e in data_dates:
        if re.match((fips if len(fips) == 2 else ("0" + fips)) + "...", data[e[0]][fips_col]):
            county = data[e[0]][county_col]
            case_total += int(data[e[0]][4])
            death_total += int(data[e[0]][5])
            if county != "Unknown":
                result[county] = (int(data[e[0]][4]), int(data[e[0]][5]))
    result["state total"] = (case_total, death_total)
    return result

def getUSAF(fips, year, month, day, case_path, death_path):
    result = {}
    case_data = openCSVAsList(case_path)
    death_data = openCSVAsList(death_path)
    fips_col = 3
    county_col = 1
    date = year + "-" + (month if len(month) == 2 else ("0" + month)) + "-" + (day if len(day) == 2 else ("0" + day))
    date_cols = find(case_data, date, count=1)
    if len(date_cols) < 1:
        return None
    date_col = date_cols[0][1]
    counties = find(case_data, fips if len(fips) == 2 else ("0" + fips))
    case_total = 0
    death_total = 0
    for e in counties:
        if e[1] == fips_col:
            county = removeLocationType(case_data[e[0]][county_col])
            case_total += int(case_data[e[0]][date_col])
            death_total += int(death_data[e[0]][date_col])
            if county != "Statewide Unallocated":
                result[county] = (int(case_data[e[0]][date_col]), int(death_data[e[0]][date_col]))
    result["state total"] = (case_total, death_total)
    return result

def print_help():
    print("To fetch data and compare:")
    print("\tCompareData.py -f <state fips> -y <year> -m <month> -d <day> -n <name of google sheet> [jhu nyt usaf]")
    print("Or")
    print("\tCompareData.py -y <year> -m <month> -d <day> -n <name of google sheet> --state_config <state config file name inside state_configs folder>")
    print("To have prompt being asked")
    print("\tCompareData.py -a")
    print("To compare without fetching, replace -n <name of google sheet> with --no_download or add --no_download")
    print("To print out the data, add -p flag")

if __name__ == "__main__":
    fips = None
    year = None
    month = None
    day = None
    sheet_name = None
    jhu = False
    nyt = False
    usaf = False
    ask = False
    print_data = False
    no_download = False
    try:
        opts, args = getopt.getopt(sys.argv[1:], "aphf:y:m:d:n:", ["state_config=", "no_download"])
    except getopt.GetoptError as err:
        print(err)
        print_help()
        sys.exit()
    path_to_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    for op, arg in opts:
        if op == "-f":
            fips = str(int(arg))
        elif op == "-y":
            year = str(int(arg))
        elif op == "-m":
            month = str(int(arg))
        elif op == "-d":
            day = str(int(arg))
        elif op == "-n":
            sheet_name = arg
        elif op == "-h":
            print_help()
            sys.exit()
        elif op == "-p":
            print_data = True
        elif op == "-a":
            ask = True
        elif op == "--no_download":
            no_download = True
        elif op == "--state_config":
            with open(os.path.join(path_to_root, "state_configs", arg)) as state_config_file:
                fips = str(int(state_config_file.readline()))
                args = [e.strip() for e in state_config_file.readlines()]
        else:
            print("unsupported option", opt)
            print_help()
            sys.exit()
    if not ask and (fips == None) | (year == None) | (month == None) | (day == None) | ((sheet_name == None) & ~no_download):
        print_help()
        sys.exit()
    if ask:
        print("enter year")
        year = str(int(input()))
        print("enter month")
        month = str(int(input()))
        print("enter day")
        day = str(int(input()))
        if not no_download:
            print("enter sheet name")
            sheet_name = input()
        print("enter state config file")
        with open(os.path.join(path_to_root, "state_configs", input())) as state_config_file:
            fips = str(int(state_config_file.readline()))
            args = [e.strip() for e in state_config_file.readlines()]
    sources_path_data_name = []
    path_to_temp = os.path.join(path_to_root, "temp")
    path_to_comparision = os.path.join(path_to_root, "comparision")
    for arg in args:
        if arg == "jhu":
            jhu_path = (os.path.join(path_to_temp, "jhu_case.csv"), os.path.join(path_to_temp, "jhu_death.csv"))
            if not no_download:
                with open(os.path.join(path_to_comparision, "jhu.txt"), "r") as file:
                    downloadURL(file.readline(), jhu_path[0])
                    downloadURL(file.readline(), jhu_path[1])
            sources_path_data_name.append((jhu_path, getJHU(fips, year, month, day, jhu_path[0], jhu_path[1]), "JHU"))
        elif arg == "nyt":
            nyt_path = os.path.join(path_to_temp, "nyt.csv")
            if not no_download:
                with open(os.path.join(path_to_comparision, "nyt.txt"), "r") as file:
                    downloadURL(file.readline(), nyt_path)
            sources_path_data_name.append((nyt_path, getNYT(fips, year, month, day, nyt_path), "NYT"))
        elif arg == "usaf":
            usaf_path = (os.path.join(path_to_temp, "usaf_case.csv"), os.path.join(path_to_temp, "usaf_death.csv"))
            if not no_download:
                with open(os.path.join(path_to_comparision, "usaf.txt"), "r") as file:
                    downloadURL(file.readline(), usaf_path[0])
                    downloadURL(file.readline(), usaf_path[1])
            sources_path_data_name.append((usaf_path, getUSAF(fips, year, month, day, usaf_path[0], usaf_path[1]), "USAF"))
    brstr_path = os.path.join(path_to_temp, "brstr.csv")
    if not no_download:
        downloadGoogleSheet(sheet_name, brstr_path, os.path.join(path_to_root, "key", "key.json"))
    brstr_data = getBrstr(fips, year, month, day, brstr_path)
    if print_data:
        print("BRSTR")
        print(brstr_data)
        for e in sources_path_data_name:
            print(e[2])
            print(e[1])
    print("county\tcase\tdeath")
    for key, value in brstr_data.items():
        case_diff = False
        death_diff = False
        comment_case = ""
        comment_death = ""
        for e in sources_path_data_name:
            if key not in e[1]:
                print(e[2], "does not have", key)
                exit()
            data_point = e[1][key]
            comment_case = comment_case + e[2] + "=" + str(data_point[0]) + " "
            comment_death = comment_death + e[2] + "=" + str(data_point[1]) + " "
            case_diff |= (value[0] != data_point[0])
            death_diff |= (value[1] != data_point[1])
        if case_diff:
            print(key + "\t" + comment_case + "cases in " + key + "\t" + ((comment_death + "deaths in " + key) if death_diff else " "))
        elif death_diff:
            print(key + "\t" + " " + "\t" + comment_death + "deaths in " + key)
