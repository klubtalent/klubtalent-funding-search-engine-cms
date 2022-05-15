import os
import xml.etree.ElementTree as element_tree
from datetime import datetime

import pdfquery
import requests


def download_pdf(logger, results_path, file_name, url, clean, quiet):
    # Define file path
    file_path = os.path.join(results_path, file_name)

    # Check if result needs to be generated
    if clean or not os.path.exists(file_path):

        download_file(
            logger=logger,
            file_path=file_path,
            url=url
        )

        if not quiet:
            logger.log_line(f"✓ Download {file_path}")
    else:
        logger.log_line(f"✓ Already exists {file_path}")


def download_file(logger, file_path, url):
    try:
        data = requests.get(url, verify=False)
        with open(file_path, 'wb') as file:
            file.write(data.content)
    except Exception as e:
        logger.log_line(f"✗️ Exception: {str(e)}")
        return None


def transform_pdf(logger, results_path, file_name_pdf, file_name_xml, clean, quiet):
    # Define file path
    file_path_pdf = os.path.join(results_path, file_name_pdf)
    file_path_xml = os.path.join(results_path, file_name_xml)

    # Check if result needs to be generated
    if clean or not os.path.exists(file_path_xml):

        # Transform PDF into xml file
        pdf = pdfquery.PDFQuery(file_path_pdf)
        pdf.load()
        pdf.tree.write(file_path_xml, pretty_print=True)

        if not quiet:
            logger.log_line(f"✓ Transform into {file_path_xml}")

        return pdf
    else:
        logger.log_line(f"✓ Already exists {file_path_xml}")


def parse_xml(workspace_path, file_name_xml):
    root = element_tree.parse(os.path.join(workspace_path, file_name_xml)).getroot()

    category = ""

    lsb_berlin_fundings = []

    # Parse page
    for page in root.findall("LTPage"):

        titles = []

        name = ""

        text_boxes = page.findall("LTRect/LTTextLineHorizontal/LTTextBoxHorizontal")

        if len(text_boxes) == 0:
            continue

        for text_box in text_boxes:
            titles.append(text_box.text)

        text_boxes = page.findall("LTRect/LTTextBoxHorizontal")

        if len(text_boxes) == 0:
            if len(titles) > 1:
                category = titles[1].lstrip().rstrip()
        else:
            name = titles[0].lstrip().rstrip().title()

        sections = {}

        # Parse text boxes
        for text_box in text_boxes:

            section = ""
            description = ""

            for text_line in text_box.findall("LTTextLineHorizontal"):
                text = text_line.text.lstrip().rstrip()
                if len(section) == 0:
                    section = text
                else:
                    description += text.removeprefix("f ")

            if section.startswith("Was gefördert wird"):
                sections["subject"] = description
            elif section.startswith("Wer wird gefördert"):
                sections["target"] = description
            elif section.startswith("Sonstige Hinweise"):
                sections["hints"] = description
            elif section.startswith("Höhe der Eigenmittel"):
                sections["equity"] = description
            elif section.startswith("Finanzierungsart"):
                sections["financing"] = description
            elif section.startswith("Antragsfrist"):
                sections["deadline"] = description
            elif section.startswith("Ansprechpartner"):
                sections["contact_person"] = description
            else:
                for contact_information in description.split("|"):
                    if contact_information.lstrip().rstrip().startswith("E-Mail"):
                        sections["mail"] = contact_information.replace("E-Mail:", "").replace(" ", "")
                    if contact_information.lstrip().rstrip().startswith("Tel"):
                        sections["phone"] = "+49" + contact_information.replace("Tel.:", "").replace(" ", "") \
                            .replace("(", "").replace(")", "").replace("-", "").removeprefix("0")

        if "subject" in sections:
            # Assemble funding
            lsb_berlin_funding = LsbBerlinFunding(
                category=category,
                name=name,
                subject=sections.get("subject", ""),
                target=sections.get("target", ""),
                hints=sections.get("hints", ""),
                equity=sections.get("equity", ""),
                financing=sections.get("financing", ""),
                deadline=sections.get("deadline", ""),
                contact_person=sections.get("contact_person", ""),
                url=sections.get("url", ""),
                phone=sections.get("phone", ""),
                mail=sections.get("mail", ""),
            )

            lsb_berlin_fundings.append(lsb_berlin_funding)

    return lsb_berlin_fundings


def generate_content(logger, results_path, funding):
    file_name = "lsb-berlin-" + funding.name.lower().replace("/", "").replace("  ", " ").replace(" ", "-").replace(
        "-–-", "-") + ".md"
    file_path = os.path.join(results_path, file_name)
    values = {}
    values_contact = {}

    if os.path.exists(file_path):

        sports = []
        types = []

        # Read existing file
        with open(file_path, 'r') as file:
            for line in file.readlines():
                if "=" in line:
                    key = line.split("=")[0].strip().replace("\"", "").replace("'", "")
                    value = line.split("=")[1].strip().replace("\"", "").replace("'", "")
                    value = str(value)

                    if key == "contact_person" or key == "url" or key == "phone" or key == "mail":
                        values_contact[key] = value
                    elif key == "sports":
                        sports_list = value.removeprefix("'").removesuffix("'").replace("[", "").replace("]", "")
                        if len(sports_list) > 0:
                            sports = sports_list.split(",")
                    elif key == "types":
                        types_list = value.removeprefix("'").removesuffix("'").replace("[", "").replace("]", "")
                        if len(types_list) > 0:
                            types = types_list.split(",")
                        pass
                    else:
                        values[key] = value

        # Update values
        if len(funding.image) > 0:
            values["image"] = funding.image
        if len(funding.name) > 0:
            values["name"] = funding.name
        if len(funding.subject) > 0:
            values["subject"] = funding.subject
        if len(funding.target) > 0:
            values["target"] = funding.target
        if len(funding.hints) > 0:
            values["hints"] = funding.hints
        if len(funding.equity) > 0:
            values["equity"] = funding.equity
        if len(funding.financing) > 0:
            values["financing"] = funding.financing
        if len(funding.deadline) > 0:
            values["deadline"] = funding.deadline
        if len(funding.region) > 0:
            values["region"] = funding.region
        if len(funding.category) > 0:
            values["category"] = funding.category.title().replace("Und", "und").replace("Des", "des")

        if len(funding.sports) > 0:
            for s in funding.sports:
                sports.append(s)
                sports = list(dict.fromkeys(sports))
        if len(funding.types) > 0:
            for t in funding.types:
                types.append(t)
                types = list(dict.fromkeys(types))

        if len(funding.contact_person) > 0:
            values_contact["contact_person"] = funding.contact_person
        if len(funding.url) > 0:
            values_contact["url"] = funding.url
        if len(funding.phone) > 0:
            values_contact["phone"] = funding.phone
        if len(funding.mail) > 0:
            values_contact["mail"] = funding.mail

        # Assemble content
        content = "+++"
        for key, value in values.items():
            content += f"\n{key} = \"{value}\""

        content += f"\nsports = ["
        for s in sports:
            if len(s) > 0:
                content += f"\"{s.replace('_', ' ')}\","
        content += "]"

        content += f"\ntypes = ["
        for t in types:
            if len(t) > 0:
                content += f"\"{t.replace('_', ' ')}\","
        content += "]"

        content += f"\nupdated = \"{funding.updated}\""

        content += "\n[contact]"
        for key, value in values_contact.items():
            content += f"\n{key} = \"{value}\""
        content += "\n+++"

        # Clean up
        content = content.replace(",]", "]")

        with open(file_path, 'w') as file:
            logger.log_line(f"✓ Generate {file_name}")
            file.write(content)


def extract_sports(subject, financing):
    sports = []

    if "Schwimm" in subject:
        sports.append("Schwimmen")
    if "Fußball" in financing:
        sports.append("Fußball")

    return sports


def extract_types(subject):
    types = []

    if "Duale Karriere" in subject:
        types.append("duale Förderung")
    if "Qualifizierungsmaßnahmen" in subject:
        types.append("Qualifizierungsmaßnahmen")
    if "niedrigschwellig" in subject:
        types.append("niedrigschwellige Angebote")
    if "temporäre Angebote" in subject:
        types.append("temporäre Angebote")
    if "Personal- sowie Sachkosten" in subject:
        types.append("Personalkosten")
        types.append("Sachkosten")
    if "Integrationsarbeit" in subject:
        types.append("Integrationsarbeit")
    if "außersportliche Angebote" in subject:
        types.append("außersportliche Angebote")
    if "Sportmaterial" in subject:
        types.append("Sportmaterial")
    if "Spielmaterial" in subject:
        types.append("Spielmaterial")
    if "Sport- und Spielmaterial" in subject:
        types.append("Sportmaterial")
        types.append("Spielmaterial")
    if "Übungsleiterhonorare" in subject:
        types.append("Übungsleiterhonorare")
    if "Tagesbetreuung" in subject:
        types.append("Betreuung")
    if "Betreuung" in subject:
        types.append("Betreuung")
    if "Verpflegung" in subject:
        types.append("Verpflegung")
    if "Personalstellen" in subject:
        types.append("Personalkosten")
    if "Veranstaltungen" in subject:
        types.append("Veranstaltungen")
    if "Feriensportangebote" in subject:
        types.append("Feriensportangebote")
    if "Leistungssport" in subject:
        types.append("Leistungssport")
    if "Trainingslager" in subject:
        types.append("Trainingslager")
    if "Lehrgänge" in subject:
        types.append("Lehrgänge")
    if "Wettkämpfe" in subject:
        types.append("Wettkämpfe")
    if "Kinder- und Jugendsport" in subject:
        types.append("Kindersport")
        types.append("Jugendsport")
    if "Übungsleiterentgelte" in subject:
        types.append("Personalkosten")
    if "Honorartrainer" in subject:
        types.append("Personalkosten")
    if "Personalausgaben" in subject:
        types.append("Personalkosten")
    if "hauptberuflich" in subject:
        types.append("Hauptamt")
    if "Frauen" in subject:
        types.append("Frauen")
    if "Ehrenamt" in subject:
        types.append("Ehrenamt")
    if "Workshops" in subject:
        types.append("Workshops")
    if "Informationsveranstaltungen" in subject:
        types.append("Informationsveranstaltungen")
    if "Beratung" in subject:
        types.append("Beratung")
    if "Mentoring" in subject:
        types.append("Mentoring")
    if "Kinder- und Jugendarbeit" in subject:
        types.append("Kindersport")
        types.append("Jugendsport")
    if "Jugendbildung" in subject:
        types.append("Jugendbildung")
    if "ehrenamtlich" in subject:
        types.append("Ehrenamt")
    if "Versicherung" in subject:
        types.append("Versicherung")
    if "GEMA-Beiträge" in subject:
        types.append("GEMA-Beiträge")
    if "Generationen-/Familiensport" in subject:
        types.append("Generationensport")
        types.append("Familiensport")
    if "Netzwerkarbeit" in subject:
        types.append("Netzwerkarbeit")
    if "Outdoorsport" in subject:
        types.append("Outdoorsport")
    if "Trendsportarten" in subject:
        types.append("Trendsportarten")
    if "Sportgeräte" in subject:
        types.append("Sportgeräte")
    if "Digitalisierung" in subject:
        types.append("Digitalisierung")
    if "Sportgroßgeräte" in subject:
        types.append("Sportgeräte")
    if "jubiläen" in subject:
        types.append("Jubiläen")
    if "Sportartikel" in subject:
        types.append("Sportartikel")
    if "Sportbekleidung" in subject:
        types.append("Sportbekleidung")
    if "Nachhaltigkeit" in subject:
        types.append("Nachhaltigkeit")
    if "Sportanlagen" in subject:
        types.append("Sportanlagen")
    if "Sportveranstaltungen" in subject:
        types.append("Veranstaltungen")
    if "Schulkinder" in subject:
        types.append("Schulsport")
    if "Vorschul" in subject:
        types.append("Vorschulsport")
    if "Talentförderung" in subject:
        types.append("Talentförderung")
    if "Verbandsbetriebs" in subject:
        types.append("Betrieb")
    if "Coach" in subject:
        types.append("Coaching")
    if "Werbemaßnahmen" in subject:
        types.append("Werbemaßnahmen")
    if "Kinder- und Jugendarbeit" in subject:
        types.append("Kinderarbeit")
        types.append("Jugendarbeit")
    if "außerhalb des sportfachlichen Betätigungsfeldes" in subject:
        types.append("außersportliche Angebote")
    if "Breitensport" in subject:
        types.append("Breitensport")
    if "Kooperationen" in subject:
        types.append("Kooperationen")

    return types


class LsbBerlinFunding:
    def __init__(self, category, name, subject, target, hints, equity, financing, deadline,
                 contact_person, url, phone, mail):
        self.category = category
        self.name = name
        self.subject = subject
        self.target = target
        self.hints = hints
        self.equity = equity
        self.financing = financing
        self.deadline = deadline

        self.region = "Berlin"
        self.sports = []
        self.types = []

        self.sports = extract_sports(subject, financing)
        self.types = extract_types(subject)

        self.contact_person = contact_person
        self.url = url
        self.phone = phone
        self.mail = mail

        self.updated = datetime.today().strftime('%d-%m-%Y')
        self.image = "/uploads/lsb_logo.png"


class LsbBerlinCrawler:
    file_name_pdf = "LSB-Foerderbroschuere.pdf"
    file_name_xml = "LSB-Foerderbroschuere.xml"
    url = f"https://lsb-berlin.net/fileadmin/redaktion/doc/broschueren/{file_name_pdf}"

    def run(self, logger, workspace_path, results_path, clean=False, quiet=False):
        # Make results path
        os.makedirs(os.path.join(workspace_path), exist_ok=True)

        download_pdf(logger, workspace_path, self.file_name_pdf, self.url, clean, quiet)
        transform_pdf(logger, workspace_path, self.file_name_pdf, self.file_name_xml, clean, quiet)

        for funding in parse_xml(workspace_path, self.file_name_xml):
            generate_content(logger, results_path, funding)
