import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import wx
import wx.adv
import threading
import webbrowser


class HelloFrame(wx.Frame):
    def __init__(self, *args, **kw):
        super(HelloFrame, self).__init__(*args, **kw)
        pnl = wx.Panel(self)

        # Title
        title = wx.StaticText(pnl, label="Wikipedia Word Scraper", style=wx.ALIGN_CENTER)
        font = title.GetFont()
        font.PointSize += 10
        font = font.Bold()
        title.SetFont(font)

        # Input box
        self.input_box = wx.TextCtrl(pnl, value="Enter word here")

        # Button
        search_btn = wx.Button(pnl, label="Search")
        search_btn.Bind(wx.EVT_BUTTON, self.on_search)

        # Status label
        self.status_label = wx.StaticText(pnl, label="")

        # Results label
        results_label = wx.StaticText(pnl, label="Results (click a link to open):")

        # Clickable links list box
        self.link_list = wx.ListBox(pnl, style=wx.LB_SINGLE)
        self.link_list.Bind(wx.EVT_LISTBOX_DCLICK, self.on_link_double_click)
        self.link_list.Bind(wx.EVT_LISTBOX, self.on_link_single_click)

        # Open button
        self.open_btn = wx.Button(pnl, label="Open Selected Link")
        self.open_btn.Bind(wx.EVT_BUTTON, self.on_open_link)
        self.open_btn.Disable()

        # Layout
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(title, 0, wx.EXPAND | wx.ALL, 10)
        sizer.Add(self.input_box, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        sizer.Add(search_btn, 0, wx.EXPAND | wx.ALL, 10)
        sizer.Add(self.status_label, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        sizer.Add(results_label, 0, wx.LEFT | wx.TOP, 10)
        sizer.Add(self.link_list, 1, wx.EXPAND | wx.ALL, 10)
        sizer.Add(self.open_btn, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        pnl.SetSizer(sizer)
        self.makeMenuBar()
        self.CreateStatusBar()
        self.SetStatusText("Ready")

        # Store found URLs
        self.found_urls = []

    def on_search(self, event):
        word = self.input_box.GetValue().strip().lower()
        if not word:
            self.status_label.SetLabel("Please enter a word.")
            return

        # Clear previous results
        self.link_list.Clear()
        self.found_urls = []
        self.open_btn.Disable()
        self.status_label.SetLabel("Scraping... please wait.")
        self.SetStatusText("Scraping...")

        # Run in background thread so UI doesn't freeze
        thread = threading.Thread(target=self.scrape, args=(word,), daemon=True)
        thread.start()

    def make_session(self):
        """Create a requests session with automatic retries."""
        session = requests.Session()
        retry = Retry(
            total=3,                  # retry up to 3 times
            backoff_factor=1,         # wait 1s, 2s, 4s between retries
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        return session

    def scrape(self, word):
        session = self.make_session()
        api_url = "https://en.wikipedia.org/w/api.php"

        # Use Wikipedia's fulltext search API — fast and reliable
        params = {
            "action": "query",
            "list": "search",
            "srsearch": word,
            "srlimit": 100,        # up to 20 results
            "srnamespace": 0,     # articles only
            "format": "json",
        }

        try:
            wx.CallAfter(self.SetStatusText, "Querying Wikipedia API...")
            response = session.get(api_url, params=params, timeout=(10, 30))
            data = response.json()

            search_results = data.get("query", {}).get("search", [])

            if not search_results:
                wx.CallAfter(self.scrape_done, [], 0)
                return

            total = len(search_results)
            for i, item in enumerate(search_results):
                title = item["title"]
                url = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
                wx.CallAfter(
                    self.SetStatusText,
                    f"Found {i + 1}/{total}: {title}"
                )
                wx.CallAfter(self.add_result, title, url)

            wx.CallAfter(self.scrape_done, search_results, 0)

        except requests.exceptions.Timeout:
            wx.CallAfter(self.scrape_error, "Request timed out. Check your connection and try again.")
        except Exception as e:
            wx.CallAfter(self.scrape_error, str(e))

    def add_result(self, title, url):
        """Called from main thread to add a result dynamically as it's found."""
        self.link_list.Append(f"{title}  →  {url}")
        self.found_urls.append(url)
        self.open_btn.Enable()

    def scrape_done(self, results, skipped=0):
        count = len(results)
        skip_note = f" ({skipped} page(s) skipped due to timeout)" if skipped else ""
        if count == 0:
            self.status_label.SetLabel(f"No matches found.{skip_note}")
            self.SetStatusText(f"Done — no matches.{skip_note}")
        else:
            self.status_label.SetLabel(f"Found {count} match{'es' if count != 1 else ''}.{skip_note} Double-click to open.")
            self.SetStatusText(f"Done — {count} result(s).{skip_note}")

    def scrape_error(self, error_msg):
        self.status_label.SetLabel(f"Error: {error_msg}")
        self.SetStatusText("Error occurred.")

    def on_link_single_click(self, event):
        self.open_btn.Enable()

    def on_link_double_click(self, event):
        self.open_selected()

    def on_open_link(self, event):
        self.open_selected()

    def open_selected(self):
        idx = self.link_list.GetSelection()
        if idx != wx.NOT_FOUND and idx < len(self.found_urls):
            webbrowser.open(self.found_urls[idx])

    def makeMenuBar(self):
        fileMenu = wx.Menu()
        exitItem = fileMenu.Append(wx.ID_EXIT)
        helpMenu = wx.Menu()
        aboutItem = helpMenu.Append(wx.ID_ABOUT)
        menuBar = wx.MenuBar()
        menuBar.Append(fileMenu, "&File")
        menuBar.Append(helpMenu, "&Help")
        self.SetMenuBar(menuBar)
        self.Bind(wx.EVT_MENU, self.OnExit, exitItem)
        self.Bind(wx.EVT_MENU, self.OnAbout, aboutItem)

    def OnExit(self, event):
        self.Close(True)

    def OnAbout(self, event):
        wx.MessageBox(
            "Wikipedia Word Scraper\n\nSearches Wikipedia article pages for a word.\n"
            "Double-click a result to open it in your browser.",
            "About",
            wx.OK | wx.ICON_INFORMATION
        )


if __name__ == '__main__':
    app = wx.App()
    frm = HelloFrame(None, title='Wikipedia Word Scraper', size=(700, 550))
    frm.Show()
    app.MainLoop()