from prompt_toolkit.shortcuts import message_dialog, input_dialog, yes_no_dialog
from prompt_toolkit.validation import Validator
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.shortcuts import radiolist_dialog
from prompt_toolkit.shortcuts import ProgressBar
from prompt_toolkit import print_formatted_text, HTML

from jinja2 import Environment, PackageLoader

from urllib.request import urlretrieve
from os import mkdir

CONTAINERS = {
    "gabriel": "Gabriel Server",
    "telemetry": "Telemetry Engine",
    "obstacle": "Avoidance Engine",
    "object": "Object Detection Engine",
    "slam": "SLAM Engine",
    "sc": "Swarm Controller",
}
TEMPLATES = {
    "template.env": ".env",
    "redis.conf.template": "./redis/redis.conf",
    "secrets.toml.template": "../../gcs/streamlit/.streamlit/secrets.toml",
}

DEFAULTS = [
    ("one_tag_to_rule_them_all", True, "Use Same Docker Tag for all components"),
    ("one_tag", "latest", "Default Docker Image Tag"),
    ("store_imagery", True, "Store Imagery Locally"),
    ("gabriel_tokens", 5, "Gabriel Server Tokens"),
    ("use_metric3d", True, "Use Metric3D"),
    ("depth_threshold", 150, "Depth Threshold"),
    ("depth_model", "metric3d_vit_large", "Depth Model"),
    ("use_custom_model", False, "Use Custom Detection Model"),
    ("detection_model", "coco", "Detection Model"),
    ("detection_threshold", 0.7, "Detection Confidence Threshold"),
    ("hsv_threshold", 0.5, "HSV Filter Threshold"),
    ("geofence", False, "Use Geofence for Detections"),
    ("object_ttl", 300, "Object TTL (sec)"),
    ("object_diff_radius", 5, "Object Diff Radius (m)"),
    ("exclusions", "", "Class Exclusions (comma-separated class ids)"),
    ("terraslam_host", "localhost", "TerraSLAM Host"),
    ("webserver_url", "localhost", "HTTP Webserver Host"),
    ("webserver_port", 8080, "HTTP Webserver Port"),
]

CONTEXT = {}

GLOBAL_STYLE = Style.from_dict(
    {
        "dialog": "bg:#636363",
        "dialog frame.label": "bg:#ffffff #000000",
        "dialog.body": "bg:#cfcfcf #111111",
        "dialog shadow": "bg:#aaaaaa",
    }
)

FORMATTED_TEXT_STYLE = Style.from_dict(
    {
        "error": "#ff0000 bold",
        "note": "#03e8fc italic",
    }
)


def write_files(CONTEXT):
    env = Environment(
        loader=PackageLoader("setup_wizard"),
    )
    with ProgressBar(
        title=HTML("<note>Writing jinja templates...</note>"),
        style=FORMATTED_TEXT_STYLE,
    ) as pb:
        for t, path in pb(TEMPLATES.items()):
            template = env.get_template(t)
            with open(path, mode="w", encoding="utf-8") as outf:
                outf.write(template.render(CONTEXT))


def download_coco_model():
    # download yolov5 coco model
    try:
        mkdir("models")
        print_formatted_text(
            HTML("<note>Created models directory.</note>"),
            style=FORMATTED_TEXT_STYLE,
        )
    except FileExistsError:
        print_formatted_text(
            HTML("<error>Models directory already exists.</error>"),
            style=FORMATTED_TEXT_STYLE,
        )
    path, _ = urlretrieve(
        "https://github.com/ultralytics/yolov5/releases/download/v7.0/yolov5m.pt",
        "./models/coco.pt",
    )
    CONTEXT["detection_model"] = "coco"
    print_formatted_text(
        HTML("<note>Downloaded YOLOv5m model to ./models/coco.pt!</note>"),
        style=FORMATTED_TEXT_STYLE,
    )


def main():
    message_dialog(
        title="SteelEagle Backend Setup Wizard",
        text="This wizard will help you configure the backend It will write several configurations files to the proper locations.",
        style=GLOBAL_STYLE,
    ).run()

    # Use DEFAULTS?
    tuple_list = []
    tuple_list.append(
        (
            "#111111",
            "Do you wish to use the following set of default values for the SteelEagle backend?\n\n",
        )
    )
    for key, value, desc in DEFAULTS:
        tuple_list.append(("#333333 italic", f"{desc}: {value}\n"))
        CONTEXT[key] = value
    print_formatted_text(
        HTML(f"<note>{CONTEXT}</note>"),
        style=FORMATTED_TEXT_STYLE,
    )
    tuple_list.append(
        (
            "#111111 bold",
            "\nNOTE: If not, you will be asked to complete the rest of the prompts of the setup wizard for each component.",
        )
    )
    defaults_text = FormattedText(tuple_list)

    CONTEXT["use_default_configuration"] = yes_no_dialog(
        title="Use Default Configuration", text=defaults_text, style=GLOBAL_STYLE
    ).run()

    if not CONTEXT["use_default_configuration"]:
        # Global
        tag_text = FormattedText(
            [
                (
                    "#111111",
                    "Do you want to use the default image tag (latest) for all SteelEagle backend components?",
                ),
                ("", "\n\n"),
                (
                    "#111111 bold",
                    f"NOTE: If not, you will be prompted to enter the tag for each SteelEagle component ({len(CONTAINERS)} components total)",
                ),
            ]
        )

        CONTEXT["one_tag_to_rule_them_all"] = yes_no_dialog(
            title="Default Docker Image Tag", text=tag_text, style=GLOBAL_STYLE
        ).run()

        if not CONTEXT["one_tag_to_rule_them_all"]:
            for container, name in CONTAINERS.items():
                CONTEXT[f"{container}_image_tag"] = input_dialog(
                    title=f"{name} Docker Image Tag",
                    text="Enter the tag for this image:",
                    style=GLOBAL_STYLE,
                ).run()
        else:  # get the one tag from input
            txt = FormattedText(
                [
                    ("#111111", "Enter the tag for "),
                    ("#111111 bold italic", "ALL "),
                    ("#111111", "images:"),
                ]
            )
            CONTEXT["one_tag"] = input_dialog(
                title="Universal Docker Image Tag",
                text=txt,
                style=GLOBAL_STYLE,
                default="latest",
            ).run()

        def is_valid_num_tokens(text):
            try:
                a = int(text)
            except ValueError:
                return False

            return a > 0 and a < 30

        txt = FormattedText(
            [
                (
                    "#111111",
                    "Do you want to use the store images locally (in steeleagle-vol/images)?",
                ),
                ("", "\n\n"),
                (
                    "#111111 bold",
                    "NOTE: If not, the Streamlit GCS will not display images from vehicles/engines.",
                ),
            ]
        )
        CONTEXT["store_imagery"] = yes_no_dialog(
            title="Store Imagery Locally", text=txt, style=GLOBAL_STYLE
        ).run()

        # Gabriel
        CONTEXT["gabriel_tokens"] = int(
            input_dialog(
                title="Gabriel - Tokens",
                text="Enter the number of tokens for the Gabriel server:",
                default="5",
                validator=Validator.from_callable(
                    is_valid_num_tokens,
                    error_message="The number of Gabriel tokens must be a positive integer between 1 and 30.",
                ),
                style=GLOBAL_STYLE,
            ).run()
        )

        # Obstacle
        txt = FormattedText(
            [
                (
                    "#111111",
                    "Do you wish to use the following set of default values for the obstacle avoidanace engine?\n\n",
                ),
                (
                    "#333333 italic",
                    "Use Metric3D\nDepth Threshold: 150 layers\nModel: metric3d_vit_large\n",
                ),
                (
                    "#111111 bold",
                    "\nNOTE: If not, you will be asked to enter the above values that configure the behavior of the obstacle avoidance engine.",
                ),
            ]
        )
        CONTEXT["use_defaults_avoidance"] = yes_no_dialog(
            title="Avoidance - Use Defaults", text=txt, style=GLOBAL_STYLE
        ).run()

        if not CONTEXT["use_defaults_avoidance"]:
            txt = FormattedText(
                [
                    ("#111111", "Do you wish to use Metric3D for obstacle avoidance? "),
                    ("", "\n\n"),
                    (
                        "#111111 bold",
                        "NOTE: Metric3D requires a GPU with much VRAM (>8GB). If you do not have a GPU that large, select no to use the lighter MiDaS network.",
                    ),
                ]
            )
            CONTEXT["use_metric3d"] = yes_no_dialog(
                title="Avoidance - Metric3D or MiDaS", text=txt, style=GLOBAL_STYLE
            ).run()

            def is_valid_depth_threshold(text):
                try:
                    a = int(text)
                except ValueError:
                    return False

                return a > 0 and a < 255

            CONTEXT["depth_threshold"] = int(
                input_dialog(
                    title="Avoidance - Depth Threshold",
                    text="Enter the number of layers in the depth map to consider when making the avoidance calculation:",
                    default="150",
                    validator=Validator.from_callable(
                        is_valid_depth_threshold,
                        error_message="The number of Gabriel tokens must be a positive integer between 1 and 255.",
                    ),
                    style=GLOBAL_STYLE,
                ).run()
            )

            if CONTEXT["use_metric3d"]:
                CONTEXT["depth_model"] = radiolist_dialog(
                    title="Avoidance - Metric3D Model ",
                    text="Which Metric3D model should be loaded?",
                    values=[
                        ("metric3d_vit_small", "VIT backbone, small"),
                        ("metric3d_vit_large", "VIT backbone, large"),
                        ("metric3d_vit_giant2", "VIT backbone, giant"),
                        ("metric3d_convnext_large", "ConvNeXt backbone, large"),
                    ],
                    default="metric3d_vit_large",
                    style=GLOBAL_STYLE,
                ).run()
            else:  # select MiDaS model
                CONTEXT["depth_model"] = radiolist_dialog(
                    title="Avoidance - MiDaS Model ",
                    text="Which MiDaS model should be loaded?",
                    values=[
                        ("MiDaS_small", "convolutional model, small"),
                        ("MiDaS", "convolutional model, large"),
                        ("DPT_Hybrid", "DPT transformer, hybrid"),
                        ("DPT_Large", "DPT transformer, large"),
                    ],
                    default="DPT_Hybrid",
                    style=GLOBAL_STYLE,
                ).run()

        # Detection
        txt = FormattedText(
            [
                ("#111111", "Do you wish to use a custom object detection model?"),
                ("", "\n\n"),
                (
                    "#111111 bold",
                    "NOTE: If not, the default YOLOv5m model based on the COCO dataset will be downloaded and used.",
                ),
            ]
        )
        CONTEXT["use_custom_model"] = yes_no_dialog(
            title="Detection - Custom Model", text=txt, style=GLOBAL_STYLE
        ).run()

        if not CONTEXT["use_custom_model"]:
            download_coco_model()
        else:
            # enter custom model name
            txt = FormattedText(
                [
                    (
                        "#111111",
                        "Enter the name of the custom model (omit the file extension):",
                    ),
                    ("", "\n\n"),
                    (
                        "#111111 bold",
                        'i.e. If your model lives at ./models/custom-model.pt, enter "custom-model"',
                    ),
                ]
            )
            CONTEXT["detection_model"] = input_dialog(
                title="Detection - Custom Model Name", text=txt, style=GLOBAL_STYLE
            ).run()

        txt = FormattedText(
            [
                (
                    "#111111",
                    "Do you wish to use the following set of default values for the object detection engine?\n\n",
                ),
                (
                    "#333333 italic",
                    "Confidence Threshold: 0.7\nGeofence: Disabled\nGeofence File: None\nObject TTL (s): 300\nObject Radius (m): 5\nClass Exclusions: None\nHSV Threshold: 0.5\n",
                ),
                (
                    "#111111 bold",
                    "\nNOTE: If not, you will be asked to enter the above values that configure the behavior of the object detection engine.",
                ),
            ]
        )
        CONTEXT["use_defaults_detection"] = yes_no_dialog(
            title="Detection - Use Defaults", text=txt, style=GLOBAL_STYLE
        ).run()

        if not CONTEXT["use_defaults_detection"]:

            def is_valid_conf_threshold(text):
                try:
                    a = float(text)
                except ValueError:
                    return False

                return a > 0.0 and a < 1.0

            CONTEXT["detection_threshold"] = float(
                input_dialog(
                    title="Detection - Confidence Threshold",
                    text="Enter the confidence threshold for the model:",
                    default="0.7",
                    validator=Validator.from_callable(
                        is_valid_conf_threshold,
                        error_message="The threshold must be a floating point number between 0.0 and 1.0.",
                    ),
                    style=GLOBAL_STYLE,
                ).run()
            )

            CONTEXT["hsv_threshold"] = float(
                input_dialog(
                    title="Detection - HSV Filter Threshold",
                    text="Enter the HSV filter threshold:",
                    default="0.5",
                    validator=Validator.from_callable(
                        is_valid_conf_threshold,
                        error_message="The threshold must be a floating point number between 0.0 and 1.0.",
                    ),
                    style=GLOBAL_STYLE,
                ).run()
            )

            CONTEXT["geofence"] = yes_no_dialog(
                title="Detection - Use Geofence", text=txt, style=GLOBAL_STYLE
            ).run()

            if CONTEXT["geofence"]:
                CONTEXT["geofence_file"] = input_dialog(
                    title="Detection - Geofence Filename",
                    text="Enter the filename for the geofence (this should reside in the backend/server/geofence directory):",
                    default="geofence.json",
                    style=GLOBAL_STYLE,
                ).run()

            def is_valid_ttl(text):
                try:
                    a = int(text)
                except ValueError:
                    return False

                return a > 0

            CONTEXT["object_ttl"] = int(
                input_dialog(
                    title="Detection - Object TTL",
                    text="Enter the object TTL (sec):",
                    default="300",
                    validator=Validator.from_callable(
                        is_valid_ttl,
                        error_message="The object TTL must be a positive integer.",
                    ),
                    style=GLOBAL_STYLE,
                ).run()
            )

            CONTEXT["object_diff_radius"] = int(
                input_dialog(
                    title="Detection - Object Diff Radius",
                    text="Enter the object diff radius (m):",
                    default="5",
                    validator=Validator.from_callable(
                        is_valid_ttl,
                        error_message="The object diff radius must be a positive integer.",
                    ),
                    style=GLOBAL_STYLE,
                ).run()
            )

            CONTEXT["exclusions"] = input_dialog(
                title="Detection - Class Exclusions",
                text="Enter a comma-separated list of class ids to exclude from detection:",
                default="0,2,4",
                style=GLOBAL_STYLE,
            ).run()

        # SLAM
        CONTEXT["terraslam_host"] = input_dialog(
            title="SLAM - TerraSLAM Host",
            text="Enter the hostname/IP where TerraSLAM resides:",
            default="localhost",
            style=GLOBAL_STYLE,
        ).run()

        # HTTP Server
        CONTEXT["webserver_url"] = input_dialog(
            title="HTTP - Webserver Host",
            text="Enter the hostname/IP where HTTP webserver resides:",
            default="localhost",
            style=GLOBAL_STYLE,
        ).run()

        def is_valid_port(text):
            try:
                a = int(text)
            except ValueError:
                return False

            return a > 1024 and a < 65535

        CONTEXT["webserver_port"] = float(
            input_dialog(
                title="HTTP - Webserver Port",
                text="Enter the port for the webserver:",
                default="8080",
                validator=Validator.from_callable(
                    is_valid_port,
                    error_message="The threshold must be a integer between 1024 and 65535.",
                ),
                style=GLOBAL_STYLE,
            ).run()
        )
    else:
        download_coco_model()

    # Always prompt for passwords, even if using default for everything else
    CONTEXT["redis_pw"] = input_dialog(
        title="Redis - Password",
        text="Enter a secure password to use for Redis:",
        default="",
        password=True,
        style=GLOBAL_STYLE,
    ).run()

    CONTEXT["streamlit_pw"] = input_dialog(
        title="Streamlit - Password",
        text="Enter a secure password to access Streamlit:",
        default="",
        password=True,
        style=GLOBAL_STYLE,
    ).run()

    write_files(CONTEXT)


if __name__ == "__main__":
    main()
