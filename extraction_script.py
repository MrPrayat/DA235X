from openai import OpenAI
import io
import requests
import fitz
import csv


client = OpenAI()

def extract_image_description():
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": "What's in this image?"},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": "https://static1.thegamerimages.com/wordpress/wp-content/uploads/2019/09/WOW-Classic-Name-Reserve-Guild-Captain.jpg?q=50&fit=crop&w=1140&h=&dpr=1.5",
                    },
                },
            ],
        }],
    )
    return response.choices[0].message.content



def is_text_pdf(url: str) -> bool:
    # Check if the PDF is text-based or image-based
    # by attempting to extract non whitespace from each page.
    # If text is found, immediately return True; otherwise,
    # continue until all pages are read and return False.
    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.RequestException as error:
        print(f"Error fetching PDF: {error}")
        return False

    pdf_data = io.BytesIO(response.content)
    try:
        doc = fitz.open("pdf", stream=pdf_data)
    except Exception as error:
        print(f"Error opening PDF: {error}")
        return False

    for page in doc:
        if page.get_text().strip():
            return True
    return False

def run_pdf_test():
    # Tests the first 15 URLs (can be changed using test_amount) in the CSV file to determine if they are text-based PDFs.
    # The CSV file should have a header with "id" and "url" columns.

    test_amount = 15

    with open("inspection_urls.csv", mode="r", encoding="utf-8-sig") as csvfile:
        reader = csv.DictReader(csvfile)
        for index, row in enumerate(reader):
            if index >= test_amount:
                break
            url = row["url"]
            result = is_text_pdf(url)
            print(f"ID {row['id']} – URL {url} is text based: {result}")


def main():
    print("Main function started.")
    # run_pdf_test()

    # # Example usage of the image description extraction function using OpenAI API
    # # with the url source hard coded inside the function for testing purposes.
    # image_description = extract_image_description()
    # print(image_description)

if __name__ == "__main__":
    main()