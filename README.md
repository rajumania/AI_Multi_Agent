# CAMPUSFLOW AI — Smart Campus Emergency Intelligence & Multi-Agent Operations
### Vignan's Foundation for Science, Technology & Research (Vignan University)
**Vadlamudi, Guntur - 522213, Andhra Pradesh, India**

---

## 🏛️ Campus Overview & Block Directory

CampusFlow AI is an autonomous, real-time emergency response and facility incident management platform deployed across the **Vignan University (Vadlamudi, Guntur)** campus.

```
                   [ Main Vadlamudi Entrance Gate (Security Alpha) ]
                                      |
                     [ Central Transport Depot & Bus Fleet ]
                                      |
       +------------------------------+------------------------------+
       |                              |                              |
[ A-Block (Admin) ]           [ NTR Central Library ]         [ H-Block (Biotech & Science) ]
- VC & Registrar Office        - Digital Library & Study       - Bio-Labs, Chemistry, Life Sci
- Central Safety & Fire Hub    - Study Halls & Knowledge Hub
       |                              |                              |
       +------------------------------+------------------------------+
       |                              |                              |
[ U-Block (Academic) ]        [ SAC & Food Court ]            [ V-Block (Mech & Civil) ]
- Computer Science (CSE)       - Student Activity Center       - Mechanical Workshops
- IT, AI & Data Science        - Central Cafeteria & Canteen   - Power & Electrical Hub
- High-Performance Labs        - First Aid Unit 1
       |                              |                              |
       +------------------------------+------------------------------+
       |                                                             |
[ NTR Convocation Hall & OAT ]                                [ Sports Complex & Stadium ]
- Major Assembly & Shelter                                    - Indoor Arena & Field
- Capacity: 1,200+                                            - First Aid Unit 2
       |                                                             |
       +------------------------------+------------------------------+
                                      |
                 [ Mahalakshmi & Vasishta Hostels Zone ]
                 - Student Residential Quarters & Health Post
                 - Campus Health & Medical Centre (Ambulance Bay)
```

### Key Campus Blocks:
1. **U-Block (University Academic Block)**: Houses CSE, IT, Artificial Intelligence, and Data Science departments, coding labs, and central server rooms.
2. **A-Block (Administrative Block)**: Vice-Chancellor's Secretariat, Registrar's Office, Dean Offices, Examination Cell, Central Security Command.
3. **H-Block (Applied Sciences & Biotech)**: Biotechnology, Science & Humanities, Chemistry, and Nanotechnology research facilities.
4. **V-Block (Visvesvaraya Engineering Block)**: Mechanical Engineering, Civil Engineering, Robotics, and Heavy Machinery Workshops.
5. **NTR Central Library**: Multi-storey library and knowledge resource center.
6. **NTR Vignan Vihar / Convocation Hall & Auditorium**: Open Air Theatre (OAT) & main auditorium for mass evacuations (Capacity: 1,200).
7. **Sports Complex & Indoor Stadium**: Multi-sport indoor arena with secondary emergency shelter capacity (Capacity: 900).
8. **Student Activity Center (SAC) & Central Cafeteria**: Student amenities, dining, and central recreation hub.
9. **Mahalakshmi Girls Hostel & Vasishta/Valmiki Boys Hostels**: On-campus residential housing for students and faculty.
10. **Campus Health & Medical Centre**: 24/7 first aid post, medical triage, and dedicated ambulance bays.
11. **Main Vadlamudi Highway Gate**: Primary security access point with automated barrier and access controls.

---

## 🤖 Multi-Agent Orchestration Architecture

The system utilizes LangGraph and specialized AI agents coordinated through a central supervisor:

- **Lead Emergency Intake & Supervisor Agent**: Ingests multi-modal reports, performs strict classification (Fire, Medical, Security, Accident, Facility, Crowd, Weather), extracts campus block locations, and assesses casualty status without assumptions.
- **Medical Response & Triage Agent**: Recommends medical dispatch, casualty triage, emergency transport, and coordinates with Campus Health Centre.
- **Security & Perimeter Agent**: Establishes safety cordons, perimeter locks, and coordinates with Security Alpha/Bravo posts.
- **Transport & Evacuation Agent**: Coordinates bus fleet, rapid evacuation vans, and manages route accessibility across Vadlamudi campus roads.
- **Communications & Public Information Agent**: Formulates campus-wide emergency broadcasts, SMS alerts, and verified updates.

---

## 🚀 Getting Started

### Backend Setup (FastAPI + LangGraph + SQLite)
```powershell
# Navigate to project root
cd "c:\Users\bingi\OneDrive - Vignan University\Desktop\genai"

# Install Python dependencies
pip install -r backend/requirements.txt

# Start backend server (Port 8000)
python -m uvicorn backend.main:app --reload --port 8000
```

### Frontend Setup (React + Vite + Leaflet)
```powershell
# Navigate to frontend
cd frontend

# Install Node dependencies
npm install

# Start Vite development server (Port 5173)
npm run dev
```

### Running Tests
```powershell
pytest
```
