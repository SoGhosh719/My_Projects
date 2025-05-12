import docx
import pdfplumber
import sqlite3
import re
import os
from typing import List, Dict, Optional

def read_docx(file_path: str) -> List[str]:
    """Read text from a .docx file, returning lines."""
    doc = docx.Document(file_path)
    lines = []
    for para in doc.paragraphs:
        if para.text.strip():
            lines.append(para.text.strip())
    return lines

def read_pdf(file_path: str) -> List[str]:
    """Read text from a PDF file, returning lines."""
    lines = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                lines.extend([line.strip() for line in text.split('\n') if line.strip()])
    return lines

def parse_resume(lines: List[str]) -> Dict[str, any]:
    """Parse resume lines into structured sections."""
    data = {
        'Education': [],
        'TechnicalSkills': [],
        'Projects': [],
        'Experience': [],
        'Certifications': []
    }
    current_section = None
    project_title = None
    project_desc = []

    for line in lines:
        # Identify section headings
        if line.upper() in ['EDUCATION', 'TECHNICAL SKILLS', 'PROJECTS', 'EXPERIENCE', 'FORAGE PROJECTS', 'MARKETING PROJECTS', 'CERTIFICATIONS']:
            current_section = line.upper()
            if current_section in ['FORAGE PROJECTS', 'MARKETING PROJECTS']:
                current_section = 'PROJECTS'  # Merge into Projects
            continue

        # Skip empty lines
        if not line.strip():
            continue

        # Parse based on current section
        if current_section == 'EDUCATION':
            if '–' in line and any(keyword in line for keyword in ['University', 'Institute', 'College']):
                institution = line.split('–')[0].strip()
                location = line.split('–')[1].strip() if len(line.split('–')) > 1 else ''
                data['Education'].append({'institution': institution, 'location': location, 'degree': '', 'dates': '', 'coursework': ''})
            elif any(keyword in line for keyword in ['Master', 'Bachelor', 'Diploma']):
                data['Education'][-1]['degree'] = line
            elif '|' in line:
                data['Education'][-1]['dates'] = line
            elif 'Relevant Coursework' in line:
                data['Education'][-1]['coursework'] = line.replace('Relevant Coursework: ', '')

        elif current_section == 'TECHNICAL SKILLS':
            if line.startswith('•'):
                category, skills = line.split(':', 1)
                category = category.replace('•', '').strip()
                skills = [s.strip() for s in skills.split(',')]
                data['TechnicalSkills'].append({'category': category, 'skills': skills})

        elif current_section == 'PROJECTS':
            # Check for project title (numbered or bold-like)
            if re.match(r'^\d+\.\s+', line) or line.isupper() or line.startswith('**'):
                if project_title and project_desc:  # Save previous project
                    data['Projects'].append({'title': project_title, 'description': ' '.join(project_desc)})
                    project_desc = []
                project_title = re.sub(r'^\d+\.\s+|^\*\*|\*\*$', '', line).strip()
            elif line.startswith('-') or line.startswith('•'):
                if project_title:
                    project_desc.append(line.replace('-', '').replace('•', '').strip())
            elif project_title:  # Handle non-bullet description
                project_desc.append(line.strip())

        elif current_section == 'EXPERIENCE':
            if '–' in line and any(keyword in line for keyword in ['India', 'USA', 'MA', 'WB', 'OD']):
                company = line.split('–')[0].strip()
                location = line.split('–')[1].strip()
                data['Experience'].append({'company': company, 'location': location, 'role': '', 'dates': '', 'responsibilities': []})
            elif any(keyword in line for keyword in ['Manager', 'Executive', 'Intern', 'Expert', 'Founder']):
                data['Experience'][-1]['role'] = line
            elif '|' in line:
                data['Experience'][-1]['dates'] = line
            elif line.startswith('-') or line.startswith('•'):
                data['Experience'][-1]['responsibilities'].append(line.replace('-', '').replace('•', '').strip())

        elif current_section == 'CERTIFICATIONS':
            if line.startswith('-') or line.startswith('•'):
                data['Certifications'].append(line.replace('-', '').replace('•', '').strip())

    # Save the last project if exists
    if project_title and project_desc:
        data['Projects'].append({'title': project_title, 'description': ' '.join(project_desc)})

    return data

def create_database(db_path: str) -> sqlite3.Connection:
    """Create SQLite database with tables for resume data."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Education (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            institution TEXT,
            location TEXT,
            degree TEXT,
            dates TEXT,
            coursework TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS TechnicalSkills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            skills TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            description TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Experience (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company TEXT,
            location TEXT,
            role TEXT,
            dates TEXT,
            responsibilities TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Certifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT
        )
    ''')

    conn.commit()
    return conn

def insert_data(conn: sqlite3.Connection, data: Dict[str, any]):
    """Insert parsed resume data into the database."""
    cursor = conn.cursor()

    # Insert Education
    for edu in data['Education']:
        cursor.execute('''
            INSERT INTO Education (institution, location, degree, dates, coursework)
            VALUES (?, ?, ?, ?, ?)
        ''', (edu['institution'], edu['location'], edu['degree'], edu['dates'], edu['coursework']))

    # Insert Technical Skills
    for skill in data['TechnicalSkills']:
        cursor.execute('''
            INSERT INTO TechnicalSkills (category, skills)
            VALUES (?, ?)
        ''', (skill['category'], ', '.join(skill['skills'])))

    # Insert Projects
    for project in data['Projects']:
        cursor.execute('''
            INSERT INTO Projects (title, description)
            VALUES (?, ?)
        ''', (project['title'], project['description']))

    # Insert Experience
    for exp in data['Experience']:
        cursor.execute('''
            INSERT INTO Experience (company, location, role, dates, responsibilities)
            VALUES (?, ?, ?, ?, ?)
        ''', (exp['company'], exp['location'], exp['role'], exp['dates'], '; '.join(exp['responsibilities'])))

    # Insert Certifications
    for cert in data['Certifications']:
        cursor.execute('''
            INSERT INTO Certifications (name)
            VALUES (?)
        ''', (cert,))

    conn.commit()

def main(file_path: str, db_path: str = 'resume.db'):
    """Main function to process resume and create database."""
    # Determine file type
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File {file_path} not found.")

    if file_path.endswith('.docx'):
        lines = read_docx(file_path)
    elif file_path.endswith('.pdf'):
        lines = read_pdf(file_path)
    else:
        raise ValueError("Unsupported file format. Use .docx or .pdf.")

    # Parse resume
    data = parse_resume(lines)

    # Create and populate database
    conn = create_database(db_path)
    insert_data(conn, data)

    # Example query to verify data
    cursor = conn.cursor()
    cursor.execute("SELECT title FROM Projects LIMIT 5")
    print("Sample Projects:", cursor.fetchall())

    cursor.execute("SELECT institution, degree FROM Education")
    print("Education:", cursor.fetchall())

    conn.close()

if __name__ == "__main__":
    try:
        # Replace with your file path
        file_path = "Master Resume.docx"
        main(file_path)
    except Exception as e:
        print(f"Error: {e}")
