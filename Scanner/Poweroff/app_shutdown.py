from flask import Flask, render_template, redirect, url_for
import os

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/shutdown', methods=['POST'])
def shutdown():
    os.system('sudo poweroff')
    return redirect(url_for('index'))

# Other routes here...

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

