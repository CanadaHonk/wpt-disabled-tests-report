#!/usr/bin/env python3

import urllib.request
import json
import re
from string import Template
from datetime import date
import html
import urllib
import time

mozillaURL = "https://searchfox.org/mozilla-central/search?q=disabled%3A&case=true&regexp=false&path=testing%2Fweb-platform%2Fmeta"
mozillaTimeoutURL = "https://searchfox.org/mozilla-central/search?q=%5C%5BTIMEOUT%2C+OK%5C%5D%7C%5C%5BOK%2C+TIMEOUT%5C%5D%7C%3A+TIMEOUT&path=testing%2Fweb-platform%2Fmeta&case=true&regexp=true"
mozillaFlakyURL = "https://searchfox.org/mozilla-central/search?q=%5C%5B%28PASS%7CFAIL%2C+PASS%29&path=testing%2Fweb-platform%2Fmeta&case=true&regexp=true"
mozillaBugzillaURL = "https://searchfox.org/mozilla-central/search?q=bugzilla&case=true&path=testing%2Fweb-platform%2Fmeta"
chromiumURL = "https://raw.githubusercontent.com/chromium/chromium/master/third_party/blink/web_tests/TestExpectations"
chromiumNeverFixTestsURL = "https://raw.githubusercontent.com/chromium/chromium/master/third_party/blink/web_tests/NeverFixTests"
chromiumSlowTestsURL = "https://raw.githubusercontent.com/chromium/chromium/master/third_party/blink/web_tests/SlowTests"
webkitURL = "https://raw.githubusercontent.com/WebKit/webkit/master/LayoutTests/TestExpectations"
flakyQuery = "q=is%3Aissue+label%3Aflaky"
wptAPIURL = "https://api.github.com/search/issues?" + flakyQuery + "+repo%3Aweb-platform-tests/wpt"
wptHTMLURL = "https://github.com/web-platform-tests/wpt/issues?utf8=%E2%9C%93&" + flakyQuery

common = []

# Retry fetching if it fails
def fetchWithRetry(url):
    remaining = 4
    sleep = 1
    response = None
    while remaining > 0:
        try:
            response = urllib.request.urlopen(url)
            break
        except:
            sleep *= 3
            remaining -= 1
            time.sleep(sleep)
            continue
    if response:
        return response
    raise Exception("Gave up fetching " + url)

# Add path to common, merging with existing if present
def addPath(bug, path, results, product, onlyBug = False):
    if path[0] != "/":
        path = "/" + path
    pathFound = False
    pathPrefix = None
    if product == "web-platform-tests" and path[-1:] == "*":
        pathPrefix = path[:-1]
    for item in common:
        if pathPrefix and item["path"].find(pathPrefix) == 0 or item["path"] == path:
            if product in item and item[product]["bug"] == None:
                item[product]["bug"] = bug
                item[product]["results"] += " " + results
            else:
                item[product] = {"bug": bug, "results": results}
            pathFound = True
    if pathFound == False and onlyBug == False:
        common.append({"path": path, product: {"bug": bug, "results": results}})

# Mozilla
def scrapeSearchFox(url, isBugzillaSearch = False, forceResult = False):
    contents = fetchWithRetry(url).readlines()
    # Extract the data, it's on a single line after a "<script>" line
    foundScript = False
    for line in contents:
        if foundScript:
            line = line.split(b"var results = ")[1][:-2]
            break
        if b"<script>" in line:
            foundScript = True
        continue

    # Massage data structure into a common format
    items = json.loads(line)["test"]["Textual Occurrences"]
    for item in items:
        line = item["lines"][0]["line"]
        values = line.split(' https://')
        results = values.pop(0)
        if len(values) > 0:
            bug = values[0].split(' ')[0]
        else:
            bug = None

        # skip fission
        if results.find("fission") != -1:
            continue

        if forceResult:
            results = forceResult

        addPath(bug, item["path"].replace("testing/web-platform/meta", "").replace(".ini", ""), results, "mozilla", isBugzillaSearch)

scrapeSearchFox(mozillaURL)
scrapeSearchFox(mozillaBugzillaURL, True)
scrapeSearchFox(mozillaTimeoutURL, False, "[ Timeout ]")
scrapeSearchFox(mozillaFlakyURL)

# Fetch and parse TestExpectations file
def extractFromTestExpectations(url, wptPrefix, product):
    contents = fetchWithRetry(url).readlines()
    for line in contents:
        if line[0:1] == b"#":
            continue
        if wptPrefix in line:
            line = str(line[:-1], 'utf-8')
            # Extract the path and expected results tokens
            match = re.search(r"^((?:webkit|crbug)[^ ]+)? ?(?:\[ (?:Release|Debug) \] )?" + str(wptPrefix, 'utf-8') + "([^ ]+) (\[.+\])", line)
            if match == None:
                continue
            bug = match.group(1)
            path = match.group(2)
            results = match.group(3)
            # Remove tags we're not interested in
            results = results.replace(" DumpJSConsoleLogInStdErr", "").replace("ImageOnly", "")
            # Don't collect stable but failing tests
            if results == "[ Failure ]" or results == "[ ]":
                continue
            addPath(bug, path, results, product)

# Chromium
extractFromTestExpectations(chromiumURL,
                            b"external/wpt/",
                            "chromium")

extractFromTestExpectations(chromiumNeverFixTestsURL,
                            b"external/wpt/",
                            "chromium")

extractFromTestExpectations(chromiumSlowTestsURL,
                            b"external/wpt/",
                            "chromium")

# WebKit
extractFromTestExpectations(webkitURL,
                            b"imported/w3c/web-platform-tests",
                            "webkit")

# web-platform-tests issues
wptIssues = json.loads(fetchWithRetry(wptAPIURL).read())["items"]
for item in wptIssues:
    match = re.search(r"^(/[^ ]+) (?:is|are) (?:disabled|flaky|slow)", item["title"])
    if match == None:
        continue
    bug = item["html_url"][len("https://"):]
    path = match.group(1)
    addPath(bug, path, None, "web-platform-tests")

# Output json file
with open('common.json', 'w') as out:
    out.write(json.dumps(common))

# Output HTML file
foundIn4 = []
foundIn3 = []
foundIn2 = []
flakyRows = []
slowRows = []
timeoutRows = []
disabledRows = []

htmlTemplate = Template(open('templates/index.html', 'r').read())
todayStr = date.today().isoformat()
theadStr = "<tr><th>Path<th>Products<th>Results<th>Bugs<th>New issue</tr>"
rowTemplate = Template("<tr><td>$path<td> $products<td> $results<td> $bugs<td> $newIssue</tr>")
issueTitleTemplate = Template("$path is $results in $products")
issueBodyTemplate = Template(open('templates/issue-body.md', 'r').read())
newIssueTemplate = Template("""<a href="https://github.com/web-platform-tests/wpt/issues/new?title=$title&amp;body=$body&amp;labels=flaky" class="gh-button">New issue</a>""")
linkPathTemplate = Template("<a href='https://wpt.fyi$path'>$path</a><br><small>$dashboards</small>")
dashboardsTemplate = Template("Test result history for: " + \
                            "<a href='https://test-results.appspot.com/dashboards/flakiness_dashboard.html#testType=webkit_layout_tests&amp;tests=external/wpt$path'>chromium</a>, " + \
                            "<a href='https://webkit-test-results.webkit.org/dashboards/flakiness_dashboard.html#tests=imported/w3c/web-platform-tests$path'>webkit</a>")

def getProducts(item):
    products = []
    for product in ("mozilla", "chromium", "webkit"):
        if product in item:
            products.append(product)
    return products

def link(url):
    if url is None:
        return "None"
    text = url.replace("bugzilla.mozilla.org/show_bug.cgi?id=", "mozilla #")
    text = text.replace("crbug.com/", "chromium #")
    text = text.replace("webkit.org/b/", "webkit #")
    text = text.replace("github.com/web-platform-tests/wpt/issues/", "web-platform-tests #")
    return "<a href='https://%s'>%s</a>" % (url, text)

def githubLink(url):
    if url is None:
        return "None"
    return "https://%s" % url

def linkPath(path):
    dashboards = dashboardsTemplate.substitute(path=path)
    return linkPathTemplate.substitute(path=path, dashboards=dashboards)

def stringify(item, products, property, joiner):
    arr = []
    for product in products:
        if property == "bug":
            if joiner == "<br> ":
                arr.append(link(item[product][property]))
            else:
                arr.append(githubLink(item[product][property]))
        else:
            arr.append(item[product][property])
    if property == "bug":
        if "web-platform-tests" in item:
            arr.append(link(item["web-platform-tests"][property]))
    return joiner.join(arr)

def shortResult(item, products):
    arr = []
    for product in products:
        result = item[product]["results"]
        if result.find("disabled") != -1 or result == "[ Skip ]" or result == "[ WontFix ]":
            arr.append("disabled")
        elif result == "[ Slow ]" or result == "[ Timeout ]":
            arr.append("slow")
        else:
            arr.append("flaky")
    # Remove duplicates
    arr = list(set(arr))
    return "/".join(arr)

for item in common:
    products = getProducts(item)
    num = len(products)
    if "web-platform-tests" in item and "bug" in item["web-platform-tests"]:
        newIssue = ""
    else:
        issueTitle = issueTitleTemplate.substitute(path=item["path"],
                                                   results=shortResult(item, products),
                                                   products=" ".join(products),
                                                   )
        dashboards = dashboardsTemplate.substitute(path=item["path"])
        issueBody = issueBodyTemplate.substitute(path=item["path"],
                                                 products=" ".join(products),
                                                 results=stringify(item, products, "results", " "),
                                                 bugs=stringify(item, products, "bug", " "),
                                                 dashboards=dashboards,
                                                 )
        newIssue = newIssueTemplate.substitute(title=urllib.parse.quote_plus(issueTitle),
                                               body=urllib.parse.quote_plus(issueBody),
                                               )
    row = rowTemplate.substitute(path=linkPath(item["path"]),
                                 products="<br> ".join(products),
                                 results=stringify(item, products, "results", "<br> "),
                                 bugs=stringify(item, products, "bug", "<br> "),
                                 newIssue=newIssue,
                                 )
    if num == 4:
        foundIn4.append(row)
    if num == 3:
        foundIn3.append(row)
    if num == 2:
        foundIn2.append(row)
    if num == 1:
        match = re.search(r"(\[ (Slow|Timeout|Skip|WontFix) \]|disabled)", item[products[0]]["results"])
        if match:
            if match.group(0) == "[ Slow ]":
                slowRows.append(row)
            elif match.group(0) == "[ Timeout ]":
                timeoutRows.append(row)
            elif match.group(0) == "disabled" or match.group(0) == "[ Skip ]" or match.group(0) == "[ WontFix ]":
                disabledRows.append(row)
            else:
               raise Exception(row)
        else:
            flakyRows.append(row)

flakyNum = len(flakyRows)
slowNum = len(slowRows)
timeoutNum = len(timeoutRows)
disabledNum = len(disabledRows)
numRows4 = len(foundIn4)
numRows3 = len(foundIn3)
numRows2 = len(foundIn2)
numRows1 = flakyNum + slowNum + timeoutNum + disabledNum

outHTML = htmlTemplate.substitute(title="Disabled/flaky/slow web-platform-tests Report",
                                  mozillaURL=html.escape(mozillaURL),
                                  chromiumURL=html.escape(chromiumURL),
                                  chromiumNeverFixTestsURL=html.escape(chromiumNeverFixTestsURL),
                                  chromiumSlowTestsURL=html.escape(chromiumSlowTestsURL),
                                  webkitURL=html.escape(webkitURL),
                                  wptHTMLURL=html.escape(wptHTMLURL),
                                  date=todayStr,
                                  thead=theadStr,
                                  numRows4=str(numRows4),
                                  rows4="\n".join(foundIn4),
                                  numRows3=str(numRows3),
                                  rows3="\n".join(foundIn3),
                                  numRows2=str(numRows2),
                                  rows2="\n".join(foundIn2),
                                  numRows1=str(numRows1),
                                  flakyNum=str(flakyNum),
                                  flakyRows="\n".join(flakyRows),
                                  slowNum=str(slowNum),
                                  slowRows="\n".join(slowRows),
                                  timeoutNum=str(timeoutNum),
                                  timeoutRows="\n".join(timeoutRows),
                                  disabledNum=str(disabledNum),
                                  disabledRows="\n".join(disabledRows),
                                  )

with open('index.html', 'w') as out:
    out.write(outHTML)

# Normalize data.csv (1 entry per day)
csvData = {}
with open('data.csv', 'r') as file:
    for line in file:
        date, values = line.split(",", maxsplit=1)
        csvData[date] = values

csvData[todayStr] = ",".join([str(numRows4), str(numRows3), str(numRows2), str(flakyNum), str(slowNum), str(timeoutNum), str(disabledNum)])

# Output CSV
with open('data.csv', 'w') as out:
    for date in csvData:
        out.write((date + "," + csvData[date]))
    out.write("\n")
