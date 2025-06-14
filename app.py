from flask import Flask, render_template, request, redirect, url_for, flash
from database import query_db # Import our database query function
import datetime

app = Flask(__name__)
# A secret key is needed for flashing messages
app.config['SECRET_KEY'] = 'your_very_secret_key_for_the_test' # CHANGE THIS IN PRODUCTION AND USE A STRONGER KEY

@app.route('/')
def index():
    """Renders the home page with links to all questions."""
    return render_template('index.html')

@app.route('/q1', methods=['GET', 'POST'])
def q1_page():
    """
    Handles both displaying the form (GET) and processing results (POST) for Question 1.
    Displays individual polling unit results.
    """
    # Only fetch polling units that actually have announced results for the dropdown
    polling_units = query_db(
        """
        SELECT DISTINCT pu.uniqueid, pu.polling_unit_name, l.lga_name, w.ward_name
        FROM polling_unit pu
        JOIN lga l ON pu.lga_id = l.lga_id
        JOIN ward w ON pu.ward_id = w.ward_id
        JOIN announced_pu_results apr ON pu.uniqueid = apr.polling_unit_uniqueid -- Join with results table
        WHERE l.state_id = 25 -- Assuming Delta State ID is 25
        ORDER BY l.lga_name, w.ward_name, pu.polling_unit_name;
        """,
        fetchall=True
    )

    results = []
    polling_unit_info = {}
    
    if request.method == 'POST':
        selected_uniqueid = request.form.get('polling_unit_uniqueid')

        if selected_uniqueid:
            # Fetch polling unit details
            pu_info = query_db(
                """
                SELECT pu.polling_unit_name, l.lga_name, w.ward_name
                FROM polling_unit pu
                JOIN lga l ON pu.lga_id = l.lga_id
                JOIN ward w ON pu.ward_id = w.ward_id
                WHERE pu.uniqueid = %s;
                """,
                (selected_uniqueid,),
                fetchone=True
            )
            if pu_info: # pu_info is a dict due to DictCursor
                polling_unit_info = {
                    'name': pu_info['polling_unit_name'],
                    'lga': pu_info['lga_name'],
                    'ward': pu_info['ward_name']
                }

            # Fetch results for the selected polling unit
            results = query_db(
                """
                SELECT party_abbreviation, party_score
                FROM announced_pu_results
                WHERE polling_unit_uniqueid = %s
                ORDER BY party_abbreviation;
                """,
                (selected_uniqueid,),
                fetchall=True
            )
            if not results:
                flash("No results found for this specific polling unit in the database.", "info")
        else:
            flash("Please select a Polling Unit.", "error")

    return render_template('q1.html', polling_units=polling_units, results=results, polling_unit_info=polling_unit_info)


@app.route('/q2', methods=['GET', 'POST'])
def q2_page():
    """
    Renders the page for Question 2: Summed results for all polling units under a particular LGA.
    Handles both GET (display form) and POST (submit form) requests.
    """
    # Always fetch LGAs for the dropdown, whether GET or POST
    lgas = query_db(
        """
        SELECT lga_id, lga_name
        FROM lga
        WHERE state_id = 25 -- Assuming Delta State ID is 25
        ORDER BY lga_name;
        """,
        fetchall=True
    )
    
    results = []
    selected_lga_name = ""

    if request.method == 'POST':
        selected_lga_id = request.form.get('lga_id')

        if selected_lga_id:
            # Get LGA name
            lga_row = query_db("SELECT lga_name FROM lga WHERE lga_id = %s;", (selected_lga_id,), fetchone=True)
            if lga_row: # lga_row is a dict due to DictCursor
                selected_lga_name = lga_row['lga_name']
            else:
                selected_lga_name = "N/A (LGA not found)"
                flash("Selected LGA not found in database.", "error")

            # Get summed results for all polling units under the selected LGA
            results = query_db(
                """
                SELECT apr.party_abbreviation, SUM(apr.party_score) as total_score
                FROM announced_pu_results apr
                JOIN polling_unit pu ON apr.polling_unit_uniqueid = pu.uniqueid
                JOIN ward w ON pu.ward_id = w.ward_id
                JOIN lga l ON w.lga_id = l.lga_id
                WHERE l.lga_id = %s
                GROUP BY apr.party_abbreviation
                ORDER BY total_score DESC;
                """,
                (selected_lga_id,),
                fetchall=True
            )
            if not results:
                flash(f"No results found for {selected_lga_name} LGA.", "info")
        else:
            flash("Please select an LGA.", "error")

    return render_template('q2.html', lgas=lgas, results=results, selected_lga_name=selected_lga_name)


@app.route('/q3', methods=['GET', 'POST'])
def q3_page():
    """
    Renders the page for Question 3: Store results for ALL parties for a new polling unit.
    Handles both GET (display form) and POST (submit form) requests.
    """
    # Fetch parties for dynamic form generation
    parties = query_db("SELECT partyid, partyname FROM party ORDER BY partyname;", fetchall=True)

    # Fetch LGAs and Wards to help user select a location for the new polling unit
    lgas = query_db("SELECT lga_id, lga_name FROM lga WHERE state_id = 25 ORDER BY lga_name;", fetchall=True)
    wards = query_db("SELECT ward_id, ward_name, lga_id FROM ward ORDER BY ward_name;", fetchall=True)

    if request.method == 'POST':
        polling_unit_name = request.form.get('polling_unit_name')
        
        # --- FIX FOR "invalid input syntax for type integer" ERROR ---
        # Convert ward_id and lga_id to integers as the DB expects integers
        ward_id = request.form.get('ward_id', type=int) 
        lga_id = request.form.get('lga_id', type=int)
        # --- END FIX ---

        entered_by = request.form.get('entered_by_user')

        # Updated validation to check for None after type conversion
        if not polling_unit_name or ward_id is None or lga_id is None or not entered_by:
            flash("All fields (Polling Unit Name, LGA, Ward, Your Name) are required and must be valid selections.", "error")
            # Re-fetch data for rendering the form again after an error
            parties = query_db("SELECT partyid, partyname FROM party ORDER BY partyname;", fetchall=True)
            lgas = query_db("SELECT lga_id, lga_name FROM lga WHERE state_id = 25 ORDER BY lga_name;", fetchall=True)
            wards = query_db("SELECT ward_id, ward_name, lga_id FROM ward ORDER BY ward_name;", fetchall=True)
            return render_template('q3.html', parties=parties, lgas=lgas, wards=wards)

        try:
            max_uniqueid_row = query_db("SELECT MAX(uniqueid) as max_id FROM polling_unit;", fetchone=True)
            max_uniqueid = max_uniqueid_row['max_id'] if max_uniqueid_row and max_uniqueid_row['max_id'] is not None else 0
            new_uniqueid = max_uniqueid + 1

            # FIX: Added 'polling_unit_description' with a default empty string to satisfy NOT NULL constraint
            inserted_polling_unit_uniqueid = query_db(
                """
                INSERT INTO polling_unit (
                    uniqueid, polling_unit_id, ward_id, lga_id, uniquewardid,
                    polling_unit_name, polling_unit_description,
                    entered_by_user, date_entered, user_ip_address
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, %s)
                RETURNING uniqueid;
                """,
                (
                    new_uniqueid,
                    new_uniqueid, # Using same as uniqueid for polling_unit_id as a placeholder
                    ward_id,      # Now correctly an integer
                    lga_id,       # Now correctly an integer
                    f"{lga_id}-{ward_id}-{new_uniqueid}", # This string is fine for a text column
                    polling_unit_name,
                    "", # Providing an empty string for the NOT NULL 'polling_unit_description'
                    entered_by,
                    request.remote_addr
                ),
                commit=True,
                fetchone=True
            )
            inserted_polling_unit_uniqueid = inserted_polling_unit_uniqueid['uniqueid']


            # Insert party scores for the new polling unit
            for party in parties:
                partyid = party['partyid']
                partyname = party['partyname']
                score_key = f'party_score_{partyid}' # Form field name for each party score
                party_score = request.form.get(score_key, type=int)

                # Only insert if a score was provided and it's a valid integer
                if party_score is not None: 
                    query_db(
                        """
                        INSERT INTO announced_pu_results (
                            polling_unit_uniqueid, party_abbreviation, party_score,
                            entered_by_user, date_entered, user_ip_address
                        ) VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP, %s);
                        """,
                        (
                            inserted_polling_unit_uniqueid,
                            partyname,
                            party_score,
                            entered_by,
                            request.remote_addr
                        ),
                        commit=True
                    )
            
            flash(f"New polling unit '{polling_unit_name}' (ID: {inserted_polling_unit_uniqueid}) and its results saved successfully!", "success")
            return redirect(url_for('q3_page'))

        except Exception as e:
            flash(f"An error occurred while saving: {e}", "error")
            print(f"Error during Q3 submission: {e}") # Log the error to console
            # Re-fetch parties, lgas, wards to re-render the form with existing data
            parties = query_db("SELECT partyid, partyname FROM party ORDER BY partyname;", fetchall=True)
            lgas = query_db("SELECT lga_id, lga_name FROM lga WHERE state_id = 25 ORDER BY lga_name;", fetchall=True)
            wards = query_db("SELECT ward_id, ward_name, lga_id FROM ward ORDER BY ward_name;", fetchall=True)
            return render_template('q3.html', parties=parties, lgas=lgas, wards=wards)

    # For GET requests or if an error occurred during POST and we re-render
    return render_template('q3.html', parties=parties, lgas=lgas, wards=wards)


if __name__ == '__main__':
    app.run(debug=True) # Set debug=False for productionfrom flask import Flask, render_template, request, redirect, url_for, flash
from database import query_db # Import our database query function
import datetime

app = Flask(__name__)
# A secret key is needed for flashing messages
app.config['SECRET_KEY'] = 'your_very_secret_key_for_the_test' # CHANGE THIS IN PRODUCTION AND USE A STRONGER KEY

@app.route('/')
def index():
    """Renders the home page with links to all questions."""
    return render_template('index.html')

@app.route('/q1', methods=['GET', 'POST'])
def q1_page():
    """
    Handles both displaying the form (GET) and processing results (POST) for Question 1.
    Displays individual polling unit results.
    """
    # Only fetch polling units that actually have announced results for the dropdown
    polling_units = query_db(
        """
        SELECT DISTINCT pu.uniqueid, pu.polling_unit_name, l.lga_name, w.ward_name
        FROM polling_unit pu
        JOIN lga l ON pu.lga_id = l.lga_id
        JOIN ward w ON pu.ward_id = w.ward_id
        JOIN announced_pu_results apr ON pu.uniqueid = apr.polling_unit_uniqueid -- Join with results table
        WHERE l.state_id = 25 -- Assuming Delta State ID is 25
        ORDER BY l.lga_name, w.ward_name, pu.polling_unit_name;
        """,
        fetchall=True
    )

    results = []
    polling_unit_info = {}
    
    if request.method == 'POST':
        selected_uniqueid = request.form.get('polling_unit_uniqueid')

        if selected_uniqueid:
            # Fetch polling unit details
            pu_info = query_db(
                """
                SELECT pu.polling_unit_name, l.lga_name, w.ward_name
                FROM polling_unit pu
                JOIN lga l ON pu.lga_id = l.lga_id
                JOIN ward w ON pu.ward_id = w.ward_id
                WHERE pu.uniqueid = %s;
                """,
                (selected_uniqueid,),
                fetchone=True
            )
            if pu_info: # pu_info is a dict due to DictCursor
                polling_unit_info = {
                    'name': pu_info['polling_unit_name'],
                    'lga': pu_info['lga_name'],
                    'ward': pu_info['ward_name']
                }

            # Fetch results for the selected polling unit
            results = query_db(
                """
                SELECT party_abbreviation, party_score
                FROM announced_pu_results
                WHERE polling_unit_uniqueid = %s
                ORDER BY party_abbreviation;
                """,
                (selected_uniqueid,),
                fetchall=True
            )
            if not results:
                flash("No results found for this specific polling unit in the database.", "info")
        else:
            flash("Please select a Polling Unit.", "error")

    return render_template('q1.html', polling_units=polling_units, results=results, polling_unit_info=polling_unit_info)


@app.route('/q2', methods=['GET', 'POST'])
def q2_page():
    """
    Renders the page for Question 2: Summed results for all polling units under a particular LGA.
    Handles both GET (display form) and POST (submit form) requests.
    """
    # Always fetch LGAs for the dropdown, whether GET or POST
    lgas = query_db(
        """
        SELECT lga_id, lga_name
        FROM lga
        WHERE state_id = 25 -- Assuming Delta State ID is 25
        ORDER BY lga_name;
        """,
        fetchall=True
    )
    
    results = []
    selected_lga_name = ""

    if request.method == 'POST':
        selected_lga_id = request.form.get('lga_id')

        if selected_lga_id:
            # Get LGA name
            lga_row = query_db("SELECT lga_name FROM lga WHERE lga_id = %s;", (selected_lga_id,), fetchone=True)
            if lga_row: # lga_row is a dict due to DictCursor
                selected_lga_name = lga_row['lga_name']
            else:
                selected_lga_name = "N/A (LGA not found)"
                flash("Selected LGA not found in database.", "error")

            # Get summed results for all polling units under the selected LGA
            results = query_db(
                """
                SELECT apr.party_abbreviation, SUM(apr.party_score) as total_score
                FROM announced_pu_results apr
                JOIN polling_unit pu ON apr.polling_unit_uniqueid = pu.uniqueid
                JOIN ward w ON pu.ward_id = w.ward_id
                JOIN lga l ON w.lga_id = l.lga_id
                WHERE l.lga_id = %s
                GROUP BY apr.party_abbreviation
                ORDER BY total_score DESC;
                """,
                (selected_lga_id,),
                fetchall=True
            )
            if not results:
                flash(f"No results found for {selected_lga_name} LGA.", "info")
        else:
            flash("Please select an LGA.", "error")

    return render_template('q2.html', lgas=lgas, results=results, selected_lga_name=selected_lga_name)


@app.route('/q3', methods=['GET', 'POST'])
def q3_page():
    """
    Renders the page for Question 3: Store results for ALL parties for a new polling unit.
    Handles both GET (display form) and POST (submit form) requests.
    """
    # Fetch parties for dynamic form generation
    parties = query_db("SELECT partyid, partyname FROM party ORDER BY partyname;", fetchall=True)

    # Fetch LGAs and Wards to help user select a location for the new polling unit
    lgas = query_db("SELECT lga_id, lga_name FROM lga WHERE state_id = 25 ORDER BY lga_name;", fetchall=True)
    wards = query_db("SELECT ward_id, ward_name, lga_id FROM ward ORDER BY ward_name;", fetchall=True)

    if request.method == 'POST':
        polling_unit_name = request.form.get('polling_unit_name')
        
        # --- FIX FOR "invalid input syntax for type integer" ERROR ---
        # Convert ward_id and lga_id to integers as the DB expects integers
        ward_id = request.form.get('ward_id', type=int) 
        lga_id = request.form.get('lga_id', type=int)
        # --- END FIX ---

        entered_by = request.form.get('entered_by_user')

        # Updated validation to check for None after type conversion
        if not polling_unit_name or ward_id is None or lga_id is None or not entered_by:
            flash("All fields (Polling Unit Name, LGA, Ward, Your Name) are required and must be valid selections.", "error")
            # Re-fetch data for rendering the form again after an error
            parties = query_db("SELECT partyid, partyname FROM party ORDER BY partyname;", fetchall=True)
            lgas = query_db("SELECT lga_id, lga_name FROM lga WHERE state_id = 25 ORDER BY lga_name;", fetchall=True)
            wards = query_db("SELECT ward_id, ward_name, lga_id FROM ward ORDER BY ward_name;", fetchall=True)
            return render_template('q3.html', parties=parties, lgas=lgas, wards=wards)

        try:
            max_uniqueid_row = query_db("SELECT MAX(uniqueid) as max_id FROM polling_unit;", fetchone=True)
            max_uniqueid = max_uniqueid_row['max_id'] if max_uniqueid_row and max_uniqueid_row['max_id'] is not None else 0
            new_uniqueid = max_uniqueid + 1

            # FIX: Added 'polling_unit_description' with a default empty string to satisfy NOT NULL constraint
            inserted_polling_unit_uniqueid = query_db(
                """
                INSERT INTO polling_unit (
                    uniqueid, polling_unit_id, ward_id, lga_id, uniquewardid,
                    polling_unit_name, polling_unit_description,
                    entered_by_user, date_entered, user_ip_address
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, %s)
                RETURNING uniqueid;
                """,
                (
                    new_uniqueid,
                    new_uniqueid, # Using same as uniqueid for polling_unit_id as a placeholder
                    ward_id,      # Now correctly an integer
                    lga_id,       # Now correctly an integer
                    f"{lga_id}-{ward_id}-{new_uniqueid}", # This string is fine for a text column
                    polling_unit_name,
                    "", # Providing an empty string for the NOT NULL 'polling_unit_description'
                    entered_by,
                    request.remote_addr
                ),
                commit=True,
                fetchone=True
            )
            inserted_polling_unit_uniqueid = inserted_polling_unit_uniqueid['uniqueid']


            # Insert party scores for the new polling unit
            for party in parties:
                partyid = party['partyid']
                partyname = party['partyname']
                score_key = f'party_score_{partyid}' # Form field name for each party score
                party_score = request.form.get(score_key, type=int)

                # Only insert if a score was provided and it's a valid integer
                if party_score is not None: 
                    query_db(
                        """
                        INSERT INTO announced_pu_results (
                            polling_unit_uniqueid, party_abbreviation, party_score,
                            entered_by_user, date_entered, user_ip_address
                        ) VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP, %s);
                        """,
                        (
                            inserted_polling_unit_uniqueid,
                            partyname,
                            party_score,
                            entered_by,
                            request.remote_addr
                        ),
                        commit=True
                    )
            
            flash(f"New polling unit '{polling_unit_name}' (ID: {inserted_polling_unit_uniqueid}) and its results saved successfully!", "success")
            return redirect(url_for('q3_page'))

        except Exception as e:
            flash(f"An error occurred while saving: {e}", "error")
            print(f"Error during Q3 submission: {e}") # Log the error to console
            # Re-fetch parties, lgas, wards to re-render the form with existing data
            parties = query_db("SELECT partyid, partyname FROM party ORDER BY partyname;", fetchall=True)
            lgas = query_db("SELECT lga_id, lga_name FROM lga WHERE state_id = 25 ORDER BY lga_name;", fetchall=True)
            wards = query_db("SELECT ward_id, ward_name, lga_id FROM ward ORDER BY ward_name;", fetchall=True)
            return render_template('q3.html', parties=parties, lgas=lgas, wards=wards)

    # For GET requests or if an error occurred during POST and we re-render
    return render_template('q3.html', parties=parties, lgas=lgas, wards=wards)


if __name__ == '__main__':
    app.run(debug=True) # Set debug=False for production