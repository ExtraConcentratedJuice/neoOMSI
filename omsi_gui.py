import PySimpleGUI as sg
import base64
import argparse
import io
import subprocess

from omsi_client import OmsiSocketClient, OmsiDataManager
from omsi_utility import parse_questions

WINDOW_ICON = base64.b64encode(open(r"matloff.png", "rb").read())


class Omsi:
    def __init__(self, hostname=None, port=None, email=None, id=None):
        self.subproc = None
        self.questions = []
        self.combo_options = []
        self.omsi_client = None
        self.data = None
        self.selected_question = 0

        self.question_box = sg.Multiline(
            expand_y=True,
            expand_x=True,
            disabled=True,
            background_color="pale turquoise",
            font=("Courier New", 14),
        )

        self.answer_box = sg.Multiline(
            key="answer_box",
            expand_y=True,
            expand_x=True,
            disabled=True,
            background_color="khaki",
            font=("Courier New", 14),
            enable_events=True,
        )

        self.input_hostname = sg.Input(hostname, expand_x=True)
        self.input_port = sg.Input(port, expand_x=True)
        self.input_email = sg.Input(email, expand_x=True)
        self.input_id = sg.Input(id, expand_x=True)

        self.button_start = sg.Button("Start")
        self.button_pdf = sg.Button("Open PDF")
        self.button_graph = sg.Button("Open R Graph")
        self.button_help = sg.Button("About / Help")
        self.button_settings = sg.Button("Settings")
        self.button_exit = sg.Button("Exit")
        self.button_compile = sg.Button("Compile", disabled=True)
        self.button_run = sg.Button("Run", disabled=True)
        self.button_save = sg.Button("Save", disabled=True)
        self.button_submit = sg.Button("Submit", button_color="green", disabled=True)

        self.text_saved = sg.Text("Unsaved")
        self.text_connected = sg.Text(
            "Connected", visible=False, expand_x=True, expand_y=True
        )

        self.combo_question = sg.Combo(
            values=["No Session"],
            default_value="No Session",
            key="question_select",
            readonly=True,
            enable_events=True,
        )

        gui_left_column = [
            [sg.Image(source=WINDOW_ICON)],
            [
                sg.Text(
                    "Remember, I am\nalways watching.",
                    text_color="red",
                    auto_size_text=True,
                )
            ],
            [
                sg.Frame(
                    "Session",
                    [
                        [sg.Text("Hostname")],
                        [self.input_hostname],
                        [sg.Text("Port")],
                        [self.input_port],
                        [sg.Text("Email")],
                        [self.input_email],
                        [sg.Text("Exam ID")],
                        [self.input_id],
                        [self.button_start, self.text_connected],
                    ],
                )
            ],
            [sg.VPush()],
            [sg.HSeparator()],
            [self.button_pdf],
            [self.button_graph],
            [sg.HSeparator()],
            [self.button_help],
            [self.button_settings],
            [self.button_exit],
        ]

        gui_right_column = [
            [
                sg.Frame(
                    "Question",
                    [
                        [self.combo_question],
                        [self.question_box],
                    ],
                    expand_y=True,
                    expand_x=True,
                )
            ],
            [
                sg.Frame(
                    "Answer",
                    [
                        [
                            self.button_compile,
                            self.button_run,
                            self.button_save,
                            self.button_submit,
                            self.text_saved,
                        ],
                        [self.answer_box],
                    ],
                    expand_y=True,
                    expand_x=True,
                )
            ],
        ]

        gui_layout = [
            [
                sg.Column(
                    gui_left_column,
                    vertical_alignment="top",
                    element_justification="center",
                ),
                sg.Column(
                    gui_right_column,
                    expand_y=True,
                    expand_x=True,
                    vertical_alignment="top",
                ),
            ],
        ]

        self.event_dispatch_table = {
            self.button_help.key: self.show_about,
            self.button_start.key: self.start_session,
            **dict.fromkeys(
                [
                    sg.WINDOW_CLOSED,
                    sg.WINDOW_CLOSE_ATTEMPTED_EVENT,
                    self.button_exit.key,
                ],
                self.show_exit,
            ),
        }

        self.in_exam_dispatch_table = {
            self.combo_question.key: lambda: self.select_question(
                self.combo_options.index(self.combo_question.get())
            ),
            self.button_run.key: lambda: self.run_answer(self.selected_question),
            self.button_save.key: lambda: self.save_answer(self.selected_question),
            self.button_submit.key: lambda: self.submit_answer(self.selected_question),
            self.answer_box.key: lambda: self.update_save_status(False),
        }

        self.window = sg.Window(
            "neoOMSI",
            gui_layout,
            default_element_size=(14, 1),
            auto_size_text=False,
            auto_size_buttons=False,
            default_button_element_size=(14, 1),
            resizable=True,
            element_justification="left",
            icon=WINDOW_ICON,
            disable_close=True,
        )

    def is_answers_disabled(self):
        return not self.is_in_exam() or self.selected_question == 0

    def is_in_exam(self):
        return self.omsi_client is not None

    def update_save_status(self, save=None):
        if save is None:
            save = self.questions[self.selected_question].get_was_saved()
        else:
            self.questions[self.selected_question].set_saved(save)

        self.text_saved.update(value="Saved" if save else "Unsaved")

    def show_about(self):
        about_layout = [
            [sg.Push(), sg.Image(WINDOW_ICON), sg.Push()],
            [
                sg.Text(
                    "neoOMSI\nAuthor: ExtraConcentratedJuice\nFun and better OMSI client that you probably shouldn't use"
                )
            ],
            [sg.Button("Close", bind_return_key=True)],
        ]

        about_window = sg.Window(
            "About", about_layout, icon=WINDOW_ICON, finalize=True, modal=True
        )

        about_window.force_focus()

        return about_window.read(close=True)

    def show_error(self, message):
        error_layout = [
            [sg.Image("error.png"), sg.Text("Error:".ljust(32) + "\n" + message)],
            [sg.Button("OK", bind_return_key=True)],
        ]

        error_window = sg.Window(
            "Error", error_layout, icon=WINDOW_ICON, finalize=True, modal=True
        )

        error_window.force_focus()

        return error_window.read(close=True)

    def show_settings(self):
        pass

    def show_exit(self):
        if (
            sg.popup_ok_cancel(
                "Are you sure you want to exit?",
                title="Exit",
                icon=WINDOW_ICON,
                image=WINDOW_ICON,
            )
            == "OK"
        ):
            exit()

    def start_session(self):
        hostname = self.input_hostname.get()
        port = self.input_port.get()
        email = self.input_email.get()
        id = self.input_id.get()

        if not port.isdigit() or int(port) < 0 or int(port) >= 65535:
            self.show_error("Port is not valid.")
            return

        if not hostname or not port or not email or not id:
            self.show_error("All fields must be filled.")
            return

        try:
            self.omsi_client = OmsiSocketClient(hostname, port, email, id)
            self.omsi_client.open()
        except Exception as e:
            self.show_error(f"Failed to open connection to server\n\n{e}")
            self.omsi_client.close()
            self.omsi_client = None
            return

        self.input_hostname.update(disabled=True, background_color="grey")
        self.input_port.update(disabled=True, background_color="grey")
        self.input_email.update(disabled=True, background_color="grey")
        self.input_id.update(disabled=True, background_color="grey")
        self.button_start.update(visible=False)
        self.text_connected.update(visible=True)

        self.data = OmsiDataManager(id)
        self.data.create_exam_dir()
        self.data.write_questions(self.omsi_client.get_exam_questions())
        # self.data.write_supp(self.omsi_client.get_supp_file())
        self.questions = parse_questions(self.data.questions_path())

        self.combo_options = [
            "Exam Information",
            *[f"Question {x}" for x in range(1, len(self.questions))],
        ]

        self.combo_question.update(values=self.combo_options)

        self.select_question(0)

    def select_question(self, index):
        self.questions[self.selected_question].set_answer(self.answer_box.get())
        self.selected_question = index

        self.answer_box.update(
            value=self.questions[index], disabled=self.is_answers_disabled()
        )
        self.button_compile.update(
            disabled=self.is_answers_disabled()
            or not self.questions[index].get_compiler()
        )
        self.button_run.update(
            disabled=self.is_answers_disabled()
            or not self.questions[index].get_has_run()
        )
        self.button_save.update(disabled=self.is_answers_disabled())
        self.button_submit.update(disabled=self.is_answers_disabled())

        self.question_box.update(value=self.questions[index].get_question())
        self.answer_box.update(value=self.questions[index].get_answer())
        self.combo_question.update(value=self.combo_options[index])
        self.update_save_status()

    def submit_answer(self, index):
        self.save_answer(index)
        self.run_answer(index)

        if len(self.questions[index].get_answer()) == 0:
            self.show_error("No answer written.")
            return

        resp = self.omsi_client.send_file_with_retry(
            f"omsi_answer{self.questions[index].get_question_number()}{self.questions[index].get_filetype()}",
            io.BytesIO(self.questions[index].get_answer().encode("utf-8")),
        )

        sg.popup(resp)

    def save_answer(self, index):
        self.questions[index].set_answer(self.answer_box.get())
        self.data.save_answer(self.questions[index])
        self.update_save_status(True)

    def run_answer(self, index):
        self.save_answer(index)
        if self.questions[index].get_has_run():
            proc = subprocess.Popen(
                self.questions[index].get_run_cmd(),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )

            out, _ = proc.communicate()

            sg.popup_scrolled(
                out.decode("utf-8"),
                title=" ".join(self.questions[index].get_run_cmd()),
                non_blocking=True,
                icon=WINDOW_ICON,
            )

    def event_loop(self, event, values):
        if event in self.event_dispatch_table:
            self.event_dispatch_table[event]()

        if self.is_in_exam() and event in self.in_exam_dispatch_table:
            self.in_exam_dispatch_table[event]()

    def run(self):
        self.window.read(timeout=0)
        self.window.maximize()

        while True:
            self.event_loop(*self.window.read(timeout=5))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="neoOMSI",
        description="Fun and better OMSI client that you probably shouldn't use",
    )

    parser.add_argument("hostname", nargs="?")
    parser.add_argument("port", nargs="?")
    parser.add_argument("email", nargs="?")
    parser.add_argument("id", nargs="?")

    args = parser.parse_args()

    Omsi(args.hostname, args.port, args.email, args.id).run()
