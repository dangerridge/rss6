import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
import email.utils as email_utils   # for RFC 822 formatting
import datetime

class AtomToRSSConverterApp:
    def __init__(self, master):
        self.master = master
        self.master.title("Atom to RSS Converter")

        # Paths
        self.input_file_path = None
        self.output_file_path = None

        # Create GUI elements
        self.create_widgets()

    def create_widgets(self):
        frame_buttons = tk.Frame(self.master)
        frame_buttons.pack(padx=10, pady=10, fill=tk.X)

        btn_select_input = tk.Button(frame_buttons, text="Select Atom XML...",
                                     command=self.select_input_file)
        btn_select_input.pack(side=tk.LEFT, padx=5)

        btn_select_output = tk.Button(frame_buttons, text="Select Output RSS...",
                                      command=self.select_output_file)
        btn_select_output.pack(side=tk.LEFT, padx=5)

        btn_process = tk.Button(frame_buttons, text="Convert & Export",
                                command=self.process_feed)
        btn_process.pack(side=tk.LEFT, padx=5)

        # Scrolled text for logs
        self.log_area = scrolledtext.ScrolledText(self.master, width=80, height=20)
        self.log_area.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

    def log(self, message):
        """Append a line to the log area."""
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)

    def select_input_file(self):
        """Choose the Atom feed XML file."""
        file_path = filedialog.askopenfilename(
            title="Select Atom feed",
            filetypes=[("XML files", "*.xml"), ("All files", "*.*")]
        )
        if file_path:
            self.input_file_path = file_path
            self.log(f"Selected input file: {file_path}")

    def select_output_file(self):
        """Pick the output RSS file name."""
        file_path = filedialog.asksaveasfilename(
            title="Save as RSS file...",
            defaultextension=".xml",
            filetypes=[("XML files", "*.xml"), ("All files", "*.*")]
        )
        if file_path:
            self.output_file_path = file_path
            self.log(f"Selected output file: {file_path}")

    def process_feed(self):
        """Convert the Atom feed into RSS 2.0 format."""
        if not self.input_file_path:
            messagebox.showerror("Error", "No input file selected.")
            return
        if not self.output_file_path:
            messagebox.showerror("Error", "No output file selected.")
            return

        # Read input
        try:
            with open(self.input_file_path, "r", encoding="utf-8") as f:
                atom_data = f.read()
        except Exception as e:
            self.log(f"ERROR reading input file: {e}")
            messagebox.showerror("File Read Error", str(e))
            return

        # Parse as XML (Atom feed)
        try:
            atom_soup = BeautifulSoup(atom_data, "xml")
        except Exception as e:
            self.log(f"ERROR parsing XML: {e}")
            messagebox.showerror("XML Parse Error", str(e))
            return

        # Prepare a skeleton RSS feed
        # (We'll build <channel> with items)
        rss_soup = BeautifulSoup(features="xml")
        rss_tag = rss_soup.new_tag("rss", version="2.0")
        # Add the content:encoded namespace for RSS
        rss_tag["xmlns:content"] = "http://purl.org/rss/1.0/modules/content/"
        rss_soup.append(rss_tag)

        channel_tag = rss_soup.new_tag("channel")
        rss_tag.append(channel_tag)

        # Populate top-level channel data from the feed <title>, <link>, etc.
        feed_title = atom_soup.find("title")
        feed_link = atom_soup.find("link", rel="alternate")
        feed_subtitle = atom_soup.find("subtitle")

        # <title>
        title_value = feed_title.get_text(strip=True) if feed_title else "Atom to RSS Feed"
        title_elem = rss_soup.new_tag("title")
        title_elem.string = title_value
        channel_tag.append(title_elem)

        # <link>
        link_value = feed_link["href"] if (feed_link and feed_link.has_attr("href")) else "http://example.com"
        link_elem = rss_soup.new_tag("link")
        link_elem.string = link_value
        channel_tag.append(link_elem)

        # <description>
        desc_value = feed_subtitle.get_text(strip=True) if feed_subtitle else "Converted from Atom feed"
        desc_elem = rss_soup.new_tag("description")
        desc_elem.string = desc_value
        channel_tag.append(desc_elem)

        # Now convert each <entry> into an <item>
        entries = atom_soup.find_all("entry")
        count_items = 0
        for entry in entries:
            item_tag = rss_soup.new_tag("item")

            # 1) <title>
            entry_title = entry.find("title")
            if entry_title:
                title_item = rss_soup.new_tag("title")
                title_item.string = entry_title.get_text(strip=True)
                item_tag.append(title_item)

            # 2) <link>
            alt_link = entry.find("link", rel="alternate")
            if alt_link and alt_link.has_attr("href"):
                link_item = rss_soup.new_tag("link")
                link_item.string = alt_link["href"]
                item_tag.append(link_item)

            # 3) <pubDate> (convert from <published> or <updated> to RFC822)
            #    Example Atom date: 2017-06-28T08:15:00.001-07:00
            #    Example RSS date: Wed, 28 Jun 2017 08:15:00 -0700
            published_tag = entry.find("published")
            updated_tag = entry.find("updated")
            date_str = None
            if published_tag and published_tag.string:
                date_str = published_tag.string.strip()
            elif updated_tag and updated_tag.string:
                date_str = updated_tag.string.strip()

            if date_str:
                try:
                    # Parse the Atom date with dateutil
                    dt = date_parser.isoparse(date_str)
                    # Format as RFC 822
                    rfc_822_date = email_utils.format_datetime(dt)
                    pub_date = rss_soup.new_tag("pubDate")
                    pub_date.string = rfc_822_date
                    item_tag.append(pub_date)
                except Exception:
                    pass

            # 4) <content:encoded> with CDATA
            content_tag = entry.find("content")
            if content_tag and content_tag.string:
                raw_html = content_tag.string
                # Wrap in CDATA:
                # Guard if raw_html might contain "]]>" already
                safe_html = raw_html.replace("]]>", "]]]]><![CDATA[>")
                cdata_str = f"<![CDATA[{safe_html}]]>"

                content_encoded = rss_soup.new_tag("content:encoded")
                content_encoded.string = cdata_str
                item_tag.append(content_encoded)

            channel_tag.append(item_tag)
            count_items += 1

        # Write the final RSS
        try:
            with open(self.output_file_path, "w", encoding="utf-8") as f_out:
                # Use prettify() or str(rss_soup)
                f_out.write(str(rss_soup.prettify()))
        except Exception as e:
            self.log(f"ERROR writing output file: {e}")
            messagebox.showerror("Write Error", str(e))
            return

        msg = f"Successfully created RSS 2.0 feed with {count_items} <item> entries."
        self.log(msg)
        messagebox.showinfo("Done", msg)

def main():
    root = tk.Tk()
    app = AtomToRSSConverterApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
