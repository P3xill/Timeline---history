import requests
import json
import plotly.graph_objects as go
import re
import time
import sys
import threading
import os

class Spinner:
    """Simple spinner to show processing activity"""
    def __init__(self, message="Processing"):
        self.spinner = ['⣾', '⣽', '⣻', '⢿', '⡿', '⣟', '⣯', '⣷']
        self.message = message
        self.busy = False
        self.thread = None

    def spin(self):
        while self.busy:
            for char in self.spinner:
                sys.stdout.write(f'\r{self.message} {char}')
                sys.stdout.flush()
                time.sleep(0.1)
                sys.stdout.write('\b' * (len(self.message) + 2))

    def start(self):
        self.busy = True
        self.thread = threading.Thread(target=self.spin)
        self.thread.start()

    def stop(self):
        self.busy = False
        if self.thread:
            self.thread.join()
        sys.stdout.write('\r' + ' ' * (len(self.message) + 2) + '\r')
        sys.stdout.flush()

def enhance_event_with_ollama(event):
    """
    Uses Ollama to enhance and structure the event description.
    """
    prompt = (
        f"Given this historical event from {event['date']}: {event['title']} - {event['description']}\n"
        "Please enhance the description to be more engaging and informative in 2-3 sentences. "
        "Return only the enhanced description, no additional commentary."
    )
    
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": "llama3",
        "prompt": prompt,
        "stream": False,
    }
    
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            enhanced_description = response.json().get("response", "").strip()
            event['description'] = enhanced_description
    except Exception as e:
        print(f"Could not enhance event description: {e}")
    
    return event

def input_timeline_events():
    """
    Allows user to input timeline events manually.
    """
    events = []
    print("\nEnter timeline events (press Enter without input when done):")
    
    while True:
        print("\nNew Event (press Enter without date to finish):")
        date = input("Date (e.g., '1945' or 'March 1945'): ").strip()
        if not date:
            break
            
        title = input("Event title: ").strip()
        description = input("Event description: ").strip()
        
        event = {
            "date": date,
            "title": title,
            "description": description
        }
        
        # Enhance the event description using Ollama
        print("Enhancing description with Ollama...")
        enhanced_event = enhance_event_with_ollama(event)
        events.append(enhanced_event)
        
        print("Event added successfully!")
    
    return events

def get_bulk_input():
    """Gets bulk input from user until double Enter is pressed."""
    print("Paste your timeline below.")
    print("Format example:")
    print("-------------------------------------------")
    print("date: 1945")
    print("Event Title")
    print("Event description goes here.")
    print("")
    print("date: March 1945")
    print("Another Event")
    print("Another description here.")
    print("")
    print("The description can span approximately 20 words.")
    print("-------------------------------------------")
    print("Paste your timeline following this format.")
    print("Press Enter twice when done:")
    print("-------------------------------------------")
    
    lines = []
    previous_line_empty = False
    
    while True:
        line = input()
        if line.strip() == "":
            if previous_line_empty:
                break
            previous_line_empty = True
        else:
            previous_line_empty = False
        lines.append(line)
    
    # Remove the last empty line
    if lines and lines[-1].strip() == "":
        lines.pop()
        
    return "\n".join(lines)

def parse_bulk_input(text):
    """
    Parses bulk input text into timeline events.
    """
    events = []
    # Normalize line endings
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    
    # Split into chunks by looking for "date:" pattern
    raw_events = re.split(r'(?=^date:)', text.strip(), flags=re.MULTILINE)
    
    for raw_event in raw_events:
        try:
            if not raw_event.strip():
                continue
                
            # Split into lines and clean up
            lines = [line.strip() for line in raw_event.split('\n') if line.strip()]
            if len(lines) < 2:
                continue
            
            # Extract date (first line, remove "date:")
            date = lines[0].replace('date:', '').strip()
            
            # Extract title (second line)
            title = lines[1].strip()
            
            # Extract description (remaining lines)
            description = ' '.join(lines[2:]).strip()
            
            if date and title:
                event = {
                    "date": date,
                    "title": title,
                    "description": description
                }
                events.append(event)
                print(f"Parsed event: {date} - {title}")
                
        except Exception as e:
            print(f"Error parsing event: {e}")
            continue
    
    print(f"Total events parsed: {len(events)}")
    return events

def enhance_timeline_with_ollama(events):
    """
    Enhances the entire timeline structure and descriptions using Ollama.
    """
    prompt = (
        "Given these timeline events, enhance and standardize their descriptions "
        "to be more engaging and informative. Keep the same dates and titles, "
        "but improve the descriptions. Return the result as a JSON array with "
        "'date', 'title', and 'description' fields:\n\n" +
        json.dumps(events, indent=2)
    )
    
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": "llama3",
        "prompt": prompt,
        "stream": False,
    }
    
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            response_text = response.json().get("response", "").strip()
            # Extract JSON array from response
            json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
            if json_match:
                enhanced_events = json.loads(json_match.group(0))
                return enhanced_events
    except Exception as e:
        print(f"Could not enhance timeline: {e}")
    
    return events  # Return original events if enhancement fails

def create_interactive_timeline(topic, events):
    """
    Create an interactive timeline visualization using Plotly and save it as HTML.
    Each event is represented as a dot on a horizontal line.
    Hovering over a dot displays the event's details in a styled box.
    """
    if not events:
        print("No events to display.")
        return
        
    # Sort events by date if possible
    try:
        events = sorted(events, key=lambda x: x.get('date', ''))
    except Exception as e:
        print("Could not sort events by date:", e)
    
    x_values = list(range(len(events)))
    y_values = [0] * len(events)
    
    # Format descriptions with line breaks to create more square-shaped text boxes
    descriptions = []
    for event in events:
        # Split description into chunks of roughly equal length
        desc_words = event['description'].split()
        chunks = []
        current_chunk = []
        current_length = 0
        target_length = 40  # Adjust this value to control text box width
        
        for word in desc_words:
            if current_length + len(word) > target_length:
                chunks.append(' '.join(current_chunk))
                current_chunk = [word]
                current_length = len(word)
            else:
                current_chunk.append(word)
                current_length += len(word) + 1
        
        if current_chunk:
            chunks.append(' '.join(current_chunk))
            
        # Create formatted description with line breaks
        formatted_desc = (
            f"<b>{event['date']}: {event['title']}</b><br><br>" + 
            '<br>'.join(chunks)
        )
        descriptions.append(formatted_desc)
    
    # Create Plotly figure
    fig = go.Figure()
    
    # Add timeline line
    fig.add_trace(go.Scatter(
        x=x_values,
        y=y_values,
        mode="lines",
        line=dict(color="blue", width=2),
        hoverinfo="skip"
    ))
    
    # Add interactive dots with styled hover
    fig.add_trace(go.Scatter(
        x=x_values,
        y=y_values,
        mode="markers",
        marker=dict(size=12, color="red"),
        customdata=descriptions,
        hovertemplate="%{customdata}<extra></extra>",
        hoverlabel=dict(
            bgcolor="white",
            font=dict(color="black", size=12),
            bordercolor="black",
            align="left"
        )
    ))
    
    # Add date labels
    fig.add_trace(go.Scatter(
        x=x_values,
        y=[-0.1] * len(events),
        mode="text",
        text=[event['date'] for event in events],
        textposition="bottom center",
        textfont=dict(size=10),
        hoverinfo="skip"
    ))
    
    # Update layout keeping original timeline size
    fig.update_layout(
        title=f"Interactive Timeline: {topic}",
        xaxis_title="",
        yaxis=dict(
            visible=False,
            range=[-0.5, 0.5]
        ),
        autosize=True,
        margin=dict(l=50, r=50, t=50, b=100),
        hovermode="closest"
    )
    
    # Save to HTML
    output_file = f"timeline_{topic.replace(' ', '_').lower()}.html"
    output_path = os.path.join(os.path.dirname(__file__), output_file)
    fig.write_html(output_path)
    print(f"\nTimeline saved as: {output_path}")
    print("Open this file in your web browser to view the interactive timeline.\n")

def main():
    # Get bulk input
    input_text = get_bulk_input()

    if not input_text.strip():
        print("No input provided. Exiting...")
        return

    topic = input("\nEnter the timeline topic: ")
    
    # Parse the bulk input into events
    spinner = Spinner("Parsing timeline")
    spinner.start()
    events = parse_bulk_input(input_text)
    spinner.stop()
    
    if not events:
        print("Could not parse any events from the input. Exiting...")
        return
        
    # Enhance the timeline with Ollama
    print("\nEnhancing timeline with Ollama...")
    spinner = Spinner("Enhancing with AI")
    spinner.start()
    events = enhance_timeline_with_ollama(events)
    spinner.stop()
    
    if not events:
        print("No events were input. Exiting...")
        return
    
    # Display text-based timeline
    print("\n=== Text-Based Timeline ===")
    print(f"Topic: {topic}\n")
    for event in events:
        print(f"{event['date']}: {event['title']}")
        print(f"Description: {event['description']}")
        print("-" * 50)
    
    # Create interactive visualization
    create_interactive_timeline(topic, events)

if __name__ == "__main__":
    main()