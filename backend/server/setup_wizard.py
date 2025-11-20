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

containers = {
    "gabriel": "Gabriel Server",
    "telemetry": "Telemetry Engine",
    "obstacle": "Avoidance Engine",
    "object": "Object Detection Engine",
    "slam": "SLAM Engine",
    "sc": "Swarm Controller",
}
templates = {
    "template.env": ".env",
    "redis.conf.template": "./redis/redis.conf",
    "secrets.toml.template": "../../gcs/streamlit/.streamlit/secrets.toml",
}
context = {}
style = Style.from_dict(
    {
        "dialog": "bg:#636363",
        "dialog frame.label": "bg:#ffffff #000000",
        "dialog.body": "bg:#cfcfcf #111111",
        "dialog shadow": "bg:#aaaaaa",
    }
)

formatted_text_style = Style.from_dict(
    {
        "error": "#ff0000 bold",
        "note": "#03e8fc italic",
    }
)


def write_files(context):
    env = Environment(
        loader=PackageLoader("setup_wizard"),
    )
    with ProgressBar(
        title=HTML("<note>Writing jinja templates...</note>"),
        style=formatted_text_style,
    ) as pb:
        for t, path in pb(templates.items()):
            template = env.get_template(t)
            with open(path, mode="w", encoding="utf-8") as outf:
                outf.write(template.render(context))


def main():
    message_dialog(
        title="SteelEagle Backend Setup Wizard",
        text="This wizard will help you configure the backend It will write several configurations files to the proper locations.",
        style=style,
    ).run()

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
                f"NOTE: If not, you will be prompted to enter the tag for each SteelEagle component ({len(containers)} components total)",
            ),
        ]
    )

    context["one_tag_to_rule_them_all"] = yes_no_dialog(
        title="Default Docker Image Tag", text=tag_text, style=style
    ).run()

    if not context["one_tag_to_rule_them_all"]:
        for container, name in containers.items():
            context[f"{container}_image_tag"] = input_dialog(
                title=f"{name} Docker Image Tag",
                text="Enter the tag for this image:",
                style=style,
            ).run()
    else:  # get the one tag from input
        txt = FormattedText(
            [
                ("#111111", "Enter the tag for "),
                ("#111111 bold italic", "ALL "),
                ("#111111", "images:"),
            ]
        )
        context["one_tag"] = input_dialog(
            title="Universal Docker Image Tag",
            text=txt,
            style=style,
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
    context["store_imagery"] = yes_no_dialog(
        title="Store Imagery Locally", text=txt, style=style
    ).run()

    # Gabriel
    context["gabriel_tokens"] = int(
        input_dialog(
            title="Gabriel - Tokens",
            text="Enter the number of tokens for the Gabriel server:",
            default="5",
            validator=Validator.from_callable(
                is_valid_num_tokens,
                error_message="The number of Gabriel tokens must be a positive integer between 1 and 30.",
            ),
            style=style,
        ).run()
    )

    # Redis
    context["redis_pw"] = input_dialog(
        title="Redis - Password",
        text="Enter a secure password to use for Redis:",
        default="",
        password=True,
        style=style,
    ).run()

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
    context["use_defaults_avoidance"] = yes_no_dialog(
        title="Avoidance - Use Defaults", text=txt, style=style
    ).run()

    if not context["use_defaults_avoidance"]:
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
        context["use_metric3d"] = yes_no_dialog(
            title="Avoidance - Metric3D or MiDaS", text=txt, style=style
        ).run()

        def is_valid_depth_threshold(text):
            try:
                a = int(text)
            except ValueError:
                return False

            return a > 0 and a < 255

        context["depth_threshold"] = int(
            input_dialog(
                title="Avoidance - Depth Threshold",
                text="Enter the number of layers in the depth map to consider when making the avoidance calculation:",
                default="150",
                validator=Validator.from_callable(
                    is_valid_depth_threshold,
                    error_message="The number of Gabriel tokens must be a positive integer between 1 and 255.",
                ),
                style=style,
            ).run()
        )

        if context["use_metric3d"]:
            context["depth_model"] = radiolist_dialog(
                title="Avoidance - Metric3D Model ",
                text="Which Metric3D model should be loaded?",
                values=[
                    ("metric3d_vit_small", "VIT backbone, small"),
                    ("metric3d_vit_large", "VIT backbone, large"),
                    ("metric3d_vit_giant2", "VIT backbone, giant"),
                    ("metric3d_convnext_large", "ConvNeXt backbone, large"),
                ],
                default="metric3d_vit_large",
                style=style,
            ).run()
        else:  # select MiDaS model
            context["depth_model"] = radiolist_dialog(
                title="Avoidance - MiDaS Model ",
                text="Which MiDaS model should be loaded?",
                values=[
                    ("MiDaS_small", "convolutional model, small"),
                    ("MiDaS", "convolutional model, large"),
                    ("DPT_Hybrid", "DPT transformer, hybrid"),
                    ("DPT_Large", "DPT transformer, large"),
                ],
                default="DPT_Hybrid",
                style=style,
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
    context["use_custom_model"] = yes_no_dialog(
        title="Detection - Custom Model", text=txt, style=style
    ).run()

    if not context["use_custom_model"]:
        # download yolov5 coco model
        try:
            mkdir("models")
            print_formatted_text(
                HTML("<note>Created models directory.</note>"),
                style=formatted_text_style,
            )
        except FileExistsError:
            print_formatted_text(
                HTML("<error>Models directory already exists.</error>"),
                style=formatted_text_style,
            )
        path, _ = urlretrieve(
            "https://github.com/ultralytics/yolov5/releases/download/v7.0/yolov5m.pt",
            "./models/coco.pt",
        )
        context["detection_model"] = "coco"
        print_formatted_text(
            HTML("<note>Downloaded YOLOv5m model to ./models/coco.pt!</note>"),
            style=formatted_text_style,
        )
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
        context["detection_model"] = input_dialog(
            title="Detection - Custom Model Name", text=txt, style=style
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
    context["use_defaults_detection"] = yes_no_dialog(
        title="Detection - Use Defaults", text=txt, style=style
    ).run()

    if not context["use_defaults_detection"]:

        def is_valid_conf_threshold(text):
            try:
                a = float(text)
            except ValueError:
                return False

            return a > 0.0 and a < 1.0

        context["detection_threshold"] = float(
            input_dialog(
                title="Detection - Confidence Threshold",
                text="Enter the confidence threshold for the model:",
                default="0.7",
                validator=Validator.from_callable(
                    is_valid_conf_threshold,
                    error_message="The threshold must be a floating point number between 0.0 and 1.0.",
                ),
                style=style,
            ).run()
        )

        context["hsv_threshold"] = float(
            input_dialog(
                title="Detection - HSV Filter Threshold",
                text="Enter the HSV filter threshold:",
                default="0.5",
                validator=Validator.from_callable(
                    is_valid_conf_threshold,
                    error_message="The threshold must be a floating point number between 0.0 and 1.0.",
                ),
                style=style,
            ).run()
        )

        context["geofence"] = yes_no_dialog(
            title="Detection - Use Geofence", text=txt, style=style
        ).run()

        if context["geofence"]:
            context["geofence_file"] = input_dialog(
                title="Detection - Geofence Filename",
                text="Enter the filename for the geofence (this should reside in the backend/server/geofence directory):",
                default="geofence.json",
                style=style,
            ).run()

        def is_valid_ttl(text):
            try:
                a = int(text)
            except ValueError:
                return False

            return a > 0

        context["object_ttl"] = int(
            input_dialog(
                title="Detection - Object TTL",
                text="Enter the object TTL (sec):",
                default="300",
                validator=Validator.from_callable(
                    is_valid_ttl,
                    error_message="The object TTL must be a positive integer.",
                ),
                style=style,
            ).run()
        )

        context["object_diff_radius"] = int(
            input_dialog(
                title="Detection - Object Diff Radius",
                text="Enter the object diff radius (m):",
                default="5",
                validator=Validator.from_callable(
                    is_valid_ttl,
                    error_message="The object diff radius must be a positive integer.",
                ),
                style=style,
            ).run()
        )

        context["exclusions"] = input_dialog(
            title="Detection - Class Exclusions",
            text="Enter a comma-separated list of class ids to exclude from detection:",
            default="0,2,4",
            style=style,
        ).run()

    # SLAM
    context["terraslam_host"] = input_dialog(
        title="SLAM - TerraSLAM Host",
        text="Enter the hostname/IP where TerraSLAM resides:",
        default="localhost",
        style=style,
    ).run()

    # HTTP Server
    context["webserver_url"] = input_dialog(
        title="HTTP - Webserver Host",
        text="Enter the hostname/IP where HTTP webserver resides:",
        default="localhost",
        style=style,
    ).run()

    def is_valid_port(text):
        try:
            a = int(text)
        except ValueError:
            return False

        return a > 1024 and a < 65535

    context["webserver_port"] = float(
        input_dialog(
            title="HTTP - Webserver Port",
            text="Enter the port for the webserver:",
            default="8080",
            validator=Validator.from_callable(
                is_valid_port,
                error_message="The threshold must be a integer between 1024 and 65535.",
            ),
            style=style,
        ).run()
    )
    write_files(context)


if __name__ == "__main__":
    main()
