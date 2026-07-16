import subprocess
import threading
from flask import Flask, render_template, jsonify, request

app = Flask(__name__)

# متغيرات عالمية لإدارة العمليات والمخرجات في الخلفية
current_process = None
output_log = []

@app.route('/')
def home():
    # استدعاء واجهة المستخدم من مجلد templates
    return render_template('index.html')

def read_output(process):
    global output_log
    # قراءة مخرجات الطرفية سطر بسطر وتخزينها
    for line in iter(process.stdout.readline, ''):
        output_log.append(line)
        if len(output_log) > 1000:
            output_log.pop(0)
    process.stdout.close()

@app.route('/run_task', methods=['POST'])
def run_task():
    global current_process, output_log
    if current_process and current_process.poll() is None:
        return jsonify({"status": "error", "message": "هناك عملية تدقيق تعمل بالفعل في الخلفية!"})

    data = request.json
    task_type = data.get('task_type')
    interface = data.get('interface', 'wlan0')
    target_ip = data.get('target_ip', '')

    # بناء أمر الفحص والتدقيق بناءً على طلب المستخدم
    if task_type == 'scan_network':
        command = f"sudo nmap -sV -F {target_ip}"
        output_log = ["[+] جاري بدء فحص الأجهزة والخدمات النشطة عبر Nmap...\n"]
    
    elif task_type == 'audit_protocols':
        command = f"sudo responder -I {interface} -wF"
        output_log = ["[+] جاري تفعيل مراقبة استجابة بروتوكولات الشبكة المحلية (Responder)...\n"]
        
    elif task_type == 'audit_wifi':
        command = f"sudo wifite -i {interface} --kill"
        output_log = ["[+] جاري تشغيل أداة مراجعة المعايير اللاسلكية (Wifite)...\n"]
    else:
        return jsonify({"status": "error", "message": "نوع العملية غير مدعوم"})

    try:
        # تشغيل الأمر في الخلفية بصلاحيات النظام
        current_process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        # تشغيل خيط معالجة منفصل لقراءة المخرجات دون تجميد الموقع
        t = threading.Thread(target=read_output, args=(current_process,))
        t.daemon = True
        t.start()
        
        return jsonify({"status": "success", "message": "تم بدء تشغيل المهمة المحددة بنجاح"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"فشل في تنفيذ الأمر: {str(e)}"})

@app.route('/stop_task', methods=['POST'])
def stop_task():
    global current_process
    if current_process and current_process.poll() is None:
        current_process.terminate()
        # تنظيف العمليات التابعة لضمان تحرير كرت الشبكة
        subprocess.run("sudo pkill -f nmap", shell=True)
        subprocess.run("sudo pkill -f responder", shell=True)
        subprocess.run("sudo pkill -f wifite", shell=True)
        return jsonify({"status": "success", "message": "تم إيقاف كافة عمليات التدقيق بنجاح"})
    return jsonify({"status": "error", "message": "لا توجد أي عمليات نشطة حالياً"})

@app.route('/logs', methods=['GET'])
def get_logs():
    global output_log
    return jsonify({"logs": output_log})

if __name__ == '__main__':
    # تشغيل الخادم على المنفذ 5000 ليكون متاحاً برقم الـ IP الخاص بالهاتف
    app.run(host='0.0.0.0', port=5000, debug=True)
