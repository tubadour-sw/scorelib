# SKG Notenbank - Music Archive Management System

A comprehensive Django-based sheet music database and archive management system designed for orchestras, concert bands, and other musical ensembles. Notenbank provides centralized management of compositions, parts, concert programs, and musician access control.

## Overview

SKG Notenbank is a web-based music library management platform that enables orchestras and bands to:
- Catalog and organize sheet music collections
- Manage concert programs and setlists
- Control access to parts based on musician instruments
- Track loans and borrowing history
- Store and stream audio recordings
- Maintain comprehensive composer, arranger, and publisher databases

## Key Features

### Music Library Management
- **Comprehensive Piece Database**: Store detailed information about compositions including title, composer, arranger, publisher, duration, and difficulty level
- **Additional Information Field**: Support for movement descriptions, alternative titles, and other supplementary notes
- **Genre Classification**: Organize pieces by multiple genres for easy filtering and discovery
- **Archive Labeling**: Assign unique archive labels to catalog and locate pieces

### Part Management
- **Digital Sheet Music Storage**: Upload and manage individual instrumental parts as PDF files
- **Smart Part Organization**: Organize parts by piece with intuitive naming conventions
- **Instrument-Based Access Control**: Restrict part downloads based on musician instrument assignments

### Concert Management
- **Program Planning**: Create concert programs with organized setlists
- **Program Duration Calculation**: Automatically calculate total concert duration
- **Concert History**: Track all pieces performed at each concert with dates and venues
- **Venue Management**: Manage concert venues and locations

### Musician & Access Control
- **User Profiles**: Create musician profiles linked to user accounts
- **Instrument Groups**: Define instrument families and assign musicians to groups
- **Flexible Access Filtering**: Filter available parts using wildcard patterns (e.g., "Trumpet*", "Flügelhorn*")
- **Full Archive Access**: Grant staff members or soloists complete archive access
- **Time-Limited Downloads**: Automatically enable part downloads for active concerts (within grace period)

### Loan & Borrowing System
- **Loan Tracking**: Record when pieces are lent to other organizations or individuals
- **Status Management**: Track whether pieces are owned, lent out, or borrowed
- **Loan History**: Maintain complete history of all loans and returns
- **Overlap Detection**: Prevent conflicting loan periods for the same piece

### Audio & Media Management
- **Concert Recordings**: Store and stream audio recordings of performances
- **Audio Downloads**: Provide secure downloads of concert recordings to authorized users
- **Recording Description**: Add descriptions and metadata to audio files

### Search & Filtering
- **Advanced Search**: Search by title, composer, arranger, archive label, or additional information
- **Multi-Filter Support**: Filter by genre, difficulty level, concert, composer, arranger, and publisher
- **Real-Time Search**: Live table search for quick piece lookup

### Administrative Tools
- **CSV Import/Export**: Bulk import pieces and musician data from CSV files
- **Merge Functions**: Consolidate duplicate composers, arrangers, publishers, and genres
- **Data Validation**: Automated checks for CSV import completeness and format
- **Dry-Run Mode**: Test musician imports without committing changes

## Technology Stack

- **Backend**: Django 3.x+ (Python)
- **Database**: SQLite (default) or PostgreSQL
- **Frontend**: Bootstrap 5, HTML5, JavaScript
- **PDF Processing**: PyPDF2 for part management
- **Authentication**: Django built-in authentication with custom permission system
- **Deployment**: Gunicorn + Nginx (production-ready configuration included)

## Installation & Setup

### Prerequisites
- Python 3.8+
- pip package manager
- Git

### Local Development Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd skg-notenbank
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure database**
   ```bash
   python manage.py migrate
   ```

5. **Create a superuser**
   ```bash
   python manage.py createsuperuser
   ```

6. **Run the development server**
   ```bash
   python manage.py runserver
   ```

   Access the application at `http://localhost:8000`

### Production Deployment

Deployment configurations for Nginx and Gunicorn are provided in the `deploy/` directory:
- `etc_nginx_sites-available_skg-notenbank` - Nginx virtual host configuration
- `etc_systemd_system_gunicorn.service` - Systemd service file for Gunicorn

## Project Structure

```
skg-notenbank/
├── scorelib/              # Main Django application
│   ├── models.py         # Database models (Piece, Part, Concert, etc.)
│   ├── views.py          # View functions and API endpoints
│   ├── admin.py          # Django admin configurations
│   ├── forms.py          # Form definitions
│   ├── urls.py           # URL routing
│   ├── utils.py          # Utility functions
│   ├── signals.py        # Django signals
│   ├── tests.py          # Unit tests
│   ├── migrations/       # Database migrations
│   └── templates/        # HTML templates
├── skg_notenbank/        # Project settings
│   ├── settings.py       # Django configuration
│   ├── urls.py           # Root URL configuration
│   ├── wsgi.py          # WSGI application
│   └── asgi.py          # ASGI application
├── templates/            # Project-wide templates
├── static/              # Static files (CSS, JavaScript)
├── media/               # User-uploaded media files
├── scripts/             # Utility scripts (backups, etc.)
├── backups/             # Database backups
├── db.sqlite3          # SQLite database (development)
├── manage.py           # Django management script
├── requirements.txt    # Python dependencies
└── README.md          # This file
```

## Usage

### For Musicians
1. **Login**: Sign in with your orchestra account
2. **Browse Archive**: Browse the sheet music library with filters
3. **Download Parts**: Download your instrumental parts for active concerts
4. **View Recordings**: Listen to and download concert recordings
5. **View Profile**: Check your assigned instrument group and archive access

### For Administrators
1. **Manage Catalog**: Add, edit, or delete pieces
2. **Upload Parts**: Upload individual instrumental parts as PDF files
3. **Create Concerts**: Plan concert programs and setlists
4. **Manage Users**: Create musician profiles and assign instruments
5. **Import Data**: Use CSV import for bulk operations
6. **Track Loans**: Record piece loans and borrowing history
7. **Generate Reports**: View concert programs and piece statistics

## Models

### Core Models
- **Piece**: Sheet music composition with metadata
- **Part**: Individual instrumental part linked to a piece
- **Composer**: Composer/composer information
- **Arranger**: Arranger information
- **Publisher**: Publisher information
- **Genre**: Music genre classification
- **InstrumentGroup**: Instrument family definitions

### Concert Models
- **Concert**: Concert event with date, venue, and program
- **ProgramItem**: Individual item in a concert program
- **AudioRecording**: Audio recording of a performance
- **LoanRecord**: Loan/borrowing history for pieces

### User Models
- **MusicianProfile**: Extended user profile with instrument assignments and access control
- **User**: Django built-in user model

## Key Features in Detail

### Access Control System
The system uses a flexible permission model:
- **Staff Members**: Full access to all administrative functions
- **Musicians with Full Archive Access**: Can download all parts regardless of active concerts
- **Regular Musicians**: Can download parts only for active/recent concerts that match their instrument group
- **Instrument Filtering**: Uses wildcard patterns (e.g., "Trumpet*") to match part names to instrument groups

### Concert Availability Logic
Pieces are available for download if:
1. The musician is a staff member, OR
2. The musician has full archive access, AND
3. The piece is linked to a concert that is within the grace period (currently 14 days from concert date)

### Loan Management
Pieces can be:
- **Owned**: Orchestra's property, may be lent to others
- **Borrowed**: Borrowed from external partners, may be returned
- System prevents overlapping loan periods and tracks complete loan history

## API Endpoints

- `GET /scorelib/` - List all pieces with filtering and search
- `GET /scorelib/piece/<id>/` - Piece detail view
- `GET /scorelib/concert/<id>/` - Concert detail view with program
- `GET /api/search/?q=<query>` - JSON search API
- `GET /scorelib/download/part/<id>/` - Download instrumental part (protected)
- `GET /scorelib/download/audio/<id>/` - Download audio recording (protected)

## Security Features

- **User Authentication**: All user-facing views require login
- **Permission Checks**: Parts and recordings are protected by access control logic
- **CSRF Protection**: Django CSRF tokens on all forms
- **SQL Injection Protection**: Django ORM parameterized queries
- **File Access Control**: Direct file downloads are validated against user permissions
- **Overlap Detection**: Prevents conflicting loan periods

## Backup & Maintenance

Automated backup scripts are provided:
- `scripts/backup_db.sh` - Database backup script
- `scripts/restore_backup.sh` - Database restore script
- `scripts/send_backup_mail.py` - Email backup notifications

## Configuration

Key configuration options in `skg_notenbank/settings.py`:
- `MEDIA_ROOT` / `MEDIA_URL` - Media file storage location
- `STATIC_ROOT` / `STATIC_URL` - Static file location
- `DATABASES` - Database configuration
- `ALLOWED_HOSTS` - Allowed hostnames (production)

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the **GNU General Public License v3.0 (GPL-3.0)**.

This means:
- ✅ **You can use** this software freely for any purpose
- ✅ **You can modify** the source code
- ✅ **You can distribute** modified versions
- ⚠️ **You must** keep the GPL-3.0 license on any derived works
- ⚠️ **You must** provide access to the source code

For full license details, see the [LICENSE](LICENSE) file in this repository or visit https://www.gnu.org/licenses/gpl-3.0.html

### Summary
SKG Notenbank is free and open-source software. We encourage orchestras, bands, and music organizations to use, modify, and improve it. Any improvements or modifications should be shared back with the community under the same GPL-3.0 license.

## Support & Contact

For issues, questions, or feature requests, please open an issue on GitHub or contact the project maintainers.

## Changelog

### Version 1.0 (January 2026)
- Initial release
- Complete piece and part management
- Concert program management
- Musician access control
- Audio recording support
- Loan tracking system
- Comprehensive search and filtering
- Administrative tools (CSV import, merge functions)

## Acknowledgments

Built and maintained by **Arno Euteneuer**.

Built for managing sheet music collections in orchestras and concert bands.

---

**Last Updated**: January 2026
