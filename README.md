# 🏆 Carrom Tournament Manager

A comprehensive web application built with Python Streamlit for managing Carrom tournaments from registration to completion. This application provides a complete solution for tournament organizers to manage participants, create matches, track winners, and generate reports.

**Live Demo**: [Deploy on Streamlit Cloud]

## Features

### 🎯 Core Features
- **Participant Management**: Import participants from Excel files or add walk-in registrations
- **Registration Desk**: Mark participants as registered when they arrive at the venue
- **Match Management**: Create singles and doubles matches, track match progress
- **Tournament Bracket**: Visual representation of tournament progress
- **Winner Tracking**: Record match winners and track tournament progression
- **Data Persistence**: All data stored in SQLite database with automatic backup
- **Reports & Export**: Generate comprehensive reports and export data to Excel

### 📊 Additional Features
- **Participant History**: View individual participant match history
- **Real-time Dashboard**: Live tournament statistics and recent activities
- **Category Support**: Men's Singles, Women's Singles, Men's Doubles, Women's Doubles, Mixed Doubles
- **Cloud Deployment**: Fully compatible with Streamlit Cloud
- **Cross-platform**: Works on any device with a web browser

## Quick Start

### For Streamlit Cloud Deployment

1. **Fork this repository** to your GitHub account
2. **Deploy on Streamlit Cloud**:
   - Go to [share.streamlit.io](https://share.streamlit.io)
   - Connect your GitHub account
   - Deploy this repository
   - The app will automatically install dependencies and start

### For Local Development

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd carrom-tournament-manager
   ```

2. **Install Required Packages**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the Application**
   ```bash
   streamlit run app.py
   ```

## How to Use

1. **Import Participants**: Upload an Excel file with participant data or add participants manually
2. **Registration Desk**: Mark participants as present when they arrive
3. **Create Matches**: Generate fixtures for different categories
4. **Track Winners**: Record match results as tournaments progress
5. **Generate Reports**: Export data and view tournament statistics

## File Structure

```
├── app.py                 # Main Streamlit application
├── fixtures_utils.py      # Utility functions for match management
├── requirements.txt       # Python dependencies
├── .streamlit/config.toml # Streamlit configuration
├── README.md             # This file
└── .gitignore            # Git ignore rules
```

## Dependencies

- streamlit==1.32.0
- pandas==2.1.0
- openpyxl==3.1.2
- plotly==5.18.0

## Features by Category

### 🏓 Tournament Categories
- Men's Singles
- Women's Singles
- Men's Doubles
- Women's Doubles
- Mixed Doubles

### 📊 Reports Available
- Participant lists by category
- Match results and winners
- Tournament progress tracking
- Downloadable Excel exports

## Notes

- **Email Functionality**: Email features (Outlook integration) are disabled in cloud deployment but work in Windows local deployment
- **Database**: Uses SQLite for data persistence, automatically creates tables on first run
- **Responsive Design**: Works on desktop, tablet, and mobile devices

## Support

For support or questions, please create an issue in the GitHub repository.

---

Built with ❤️ using Python and Streamlit

5. **Access the Application**
   - Open your web browser and go to `http://localhost:8501`
   - The application will automatically open in your default browser

## Usage Guide

### 1. Import Participants
- **Download Template**: Get the Excel template from the "Import Participants" page
- **Prepare Data**: Fill in participant details (ID, Name, Gender, Category, Slot, Partner ID)
- **Upload File**: Upload your Excel file to import all participants at once

### 2. Registration Desk
- **Register Participants**: Mark participants as registered when they arrive
- **Walk-in Registration**: Add participants who weren't in the original list
- **Track Attendance**: Monitor who has registered and when

### 3. Match Management
- **Create Matches**: Pair participants for matches based on category
- **Singles Matches**: Create 1v1 matches for individual categories
- **Doubles Matches**: Create team matches for doubles categories
- **Record Winners**: Mark match winners when games are completed

### 4. Tournament Bracket
- **Visual Progress**: See tournament progression in bracket format
- **Category View**: View brackets for each category separately
- **Match Status**: Track completed and pending matches

### 5. Reports & Export
- **Tournament Summary**: View overall tournament statistics
- **Export Data**: Download participant and match data as Excel files
- **Category Analysis**: See category-wise match completion rates

## File Structure

```
Streamlit_app/
├── app.py                      # Main application file
├── requirements.txt            # Python dependencies
├── create_sample_data.py      # Script to generate sample data
├── sample_tournament_data.xlsx # Sample data for testing
├── tournament_data.db         # SQLite database (auto-created)
└── README.md                  # This file
```

## Excel File Format

The application expects Excel files with the following columns:

| Column     | Description                    | Example          |
|------------|--------------------------------|------------------|
| ID         | Unique participant identifier  | 1, 2, 3...       |
| Name       | Participant's full name        | John Doe         |
| Gender     | Male or Female                 | Male             |
| Category   | Tournament category            | Mens Singles     |
| Slot       | Time slot preference           | Morning          |
| Partner ID | Partner's ID (for doubles)     | 0 (if singles)   |

### Supported Categories
- **Mens Singles**: Individual male participants
- **Womens Singles**: Individual female participants  
- **Mens Doubles**: Two male participants per team
- **Womens Doubles**: Two female participants per team
- **Mixed Doubles**: One male and one female per team

## Database Schema

The application uses SQLite database with the following tables:

### Participants Table
- `id`: Primary key
- `name`: Participant name
- `gender`: Male/Female
- `category`: Tournament category
- `slot`: Time slot
- `partner_id`: Partner ID for doubles
- `registered_at_desk`: Registration status
- `registration_time`: Registration timestamp

### Matches Table
- `id`: Auto-increment primary key
- `category`: Match category
- `round_number`: Tournament round
- Player/team IDs for participants
- `winner_id`/`winner_team`: Winner information
- `match_status`: scheduled/completed
- Timestamps for creation and completion

## Data Safety Features

### Automatic Backup
- All data automatically saved to SQLite database
- Data persists even if application is closed unexpectedly
- No data loss during network interruptions

### Offline Support
- Application works without internet connection
- All operations stored locally
- Data can be exported for external backup

### Recovery
- Database file can be backed up manually
- Data can be exported to Excel for additional safety
- Application recreates database if corrupted

## Troubleshooting

### Common Issues

1. **Module Not Found Error**
   ```bash
   pip install streamlit pandas openpyxl plotly
   ```

2. **Port Already in Use**
   ```bash
   streamlit run app.py --server.port 8502
   ```

3. **Database Permission Error**
   - Ensure write permissions in application directory
   - Run as administrator if necessary

4. **Excel File Not Loading**
   - Check file format (.xlsx or .xls)
   - Verify all required columns are present
   - Ensure no empty rows in data

### Performance Tips
- For large tournaments (100+ participants), consider clearing old data periodically
- Export important data before major operations
- Keep database file size manageable by archiving completed tournaments

## Future Enhancements

### Planned Features
- **Email Integration**: Automatic winner notifications via Outlook/Gmail
- **Advanced Reporting**: PDF reports with tournament summaries
- **Mobile Optimization**: Enhanced mobile device support
- **Multi-tournament Support**: Manage multiple tournaments simultaneously
- **User Authentication**: Admin login and user roles
- **Real-time Sync**: Multi-device synchronization

### Email Notification Setup (Coming Soon)
The application includes framework for email notifications:
- SMTP configuration interface ready
- Winner notification templates prepared
- Manual trigger system implemented
- Outlook integration planned

## Support

### Getting Help
1. Check this README for common solutions
2. Verify all dependencies are installed correctly
3. Ensure Python version compatibility (3.8+)
4. Check file permissions and directory access

### Data Export
Before reporting issues, export your data using the "Reports & Export" feature to prevent data loss.

## Technical Details

### Technologies Used
- **Frontend**: Streamlit (Python web framework)
- **Database**: SQLite (embedded database)
- **Data Processing**: Pandas (data manipulation)
- **Visualization**: Plotly (interactive charts)
- **File Handling**: OpenPyXL (Excel file processing)

### System Requirements
- **Operating System**: Windows, macOS, or Linux
- **Memory**: Minimum 2GB RAM
- **Storage**: 100MB free space
- **Network**: Optional (for initial setup only)

## License

This application is developed for internal use at Cognizant for Carrom Tournament management.

## Version History

### v1.0 (Current)
- Complete tournament management system
- Participant registration and match management
- Data persistence and export features
- Tournament bracket visualization
- Reports and analytics

---

**Developed for Carrom Tournament Management**  
*Streamlit Application - July 2025*
