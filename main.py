from flask import Flask, render_template, request, session, redirect, url_for, flash
from atproto import Client, models
import datetime
import time

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Change this for production!


class BskyManager:
    def __init__(self):
        self.client = None
        self.status = "Ready"

    def login(self, pds, user, password):
        self.client = Client(pds)
        self.client.login(user, password)
        session['pds_url'] = pds
        session['session_string'] = self.client.export_session_string()

    def gather_followers(self, actor):
        self.status = f"Gathering followers for {actor}..."
        cursor = None
        dids = []
        print("Gathering Followers")
        while True:
            response = self.client.app.bsky.graph.get_followers(
                params=models.app.bsky.graph.get_followers.Params(
                    actor=actor,
                    cursor=cursor,
                    limit=100
                )
            )

            cursor = response.cursor

            did_i = [f.did for f in response.followers]
            dids.extend(did_i)

            if not cursor:
                break
        print("Followers Gathered")
        return dids

    def spam_list_items(self, dids, target_list):
        self.status = f"Updating list items ({len(dids)} entries)..."
        created_at = self.client.get_current_time_iso()
        list_items = [models.AppBskyGraphListitem.Record(
            created_at=created_at,
            list=target_list,
            subject=did
        ) for did in dids]

        list_of_writes = [
            models.com.atproto.repo.apply_writes.Create(
                collection="app.bsky.graph.listitem",
                value=l_i
            )
            for l_i in list_items
        ]

        def split_list(lst, n):
            return [lst[i:i+n] for i in range(0, len(lst), n)]

        splitty = split_list(list_of_writes, 200)

        print("Spamming!")
        for i, s in enumerate(splitty):
            self.client.com.atproto.repo.apply_writes(
                data=models.com.atproto.repo.apply_writes.Data(
                    repo=self.client._session.did,
                    writes=s
                )
            )
            print(f"spammed! {i}")

    def save_truckers(self, actor, repo):
        self.status = "Saving truckers..."
        # ... (your existing save_truckers code) ...


bsky = BskyManager()


@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        try:
            bsky.login(
                request.form['pds_url'],
                request.form['username'],
                request.form['password']
            )
            return redirect(url_for('dashboard'))
        except Exception as e:
            flash(f'Login failed: {str(e)}', 'danger')
    return render_template('login.html')


@app.route('/dashboard')
def dashboard():
    if 'session_string' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html', status=bsky.status)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/run_operation/<operation>', methods=['GET', 'POST'])
def run_operation(operation):
    if 'session_string' not in session:
        return redirect(url_for('login'))

    def background_task():
        try:
            bsky.client = Client(session['pds_url'])
            bsky.client.login(session_string=session['session_string'])

            if operation == 'custom_list':
                # Get form data
                target_list = request.form['target_list'].strip()
                inclusion = request.form['inclusion_dids'].split('\n')
                exclusion = request.form['exclusion_dids'].split('\n')

                # Validate target list
                if not target_list.startswith('at://'):
                    raise ValueError(
                        "Target list must start with at://! 💫 Example: at://did:plc:.../app.bsky.graph.list/...")

                # Clean DID lists
                _inclusion = [did.strip()
                              for did in inclusion if did.strip().startswith('did:')]
                _exclusion = [did.strip()
                              for did in exclusion if did.strip().startswith('did:')]

                if not _inclusion:
                    raise ValueError("Please provide some DIDs to include! 🌸")
                    inclusion = []
                for did in _inclusion:
                    inclusion.extend(bsky.gather_followers(did))
                exclusion = []
                for did in _exclusion:
                    exclusion.extend(bsky.gather_followers(did))

                    # Process DIDs
                dids = list(set(inclusion) - set(exclusion))
                if not dids:
                    raise ValueError("No DIDs left after exclusion! 🎀")

                bsky.spam_list_items(dids, target_list)

            # ... rest of existing operations ...

            flash(f'Successfully updated list {target_list}! 🌸', 'success')
        except Exception as e:
            flash(f'Error: {str(e)}', 'danger')
        finally:
            bsky.status = "Ready"
    background_task()
    return redirect(url_for('dashboard'))


if __name__ == '__main__':
    app.run(debug=True)
    app.run(debug=True)
