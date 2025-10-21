---
sidebar_position: 3
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Python Package

SteelEagle provides a Python package, `steeleagle_sdk`, to make it easier to develop for and interact with SteelEagle modules through Python.
The package contains the following contents:
- [**api**](python/steeleagle_sdk/api): A Pydantic type-checked API for working with SteelEagle gRPC vehicle services
- [**dsl**](python/steeleage_sdk/dsl): A compiler for creating a finite state machine runnable mission from a SteelEagle DSL specification
- [**protocol**](python/steeleagle_sdk/protocol): Low-level protocol bindings for gRPC and SteelEagle messages (only for advanced use-cases)
- [**tools**](python/steeleagle_sdk/tools): Extra tools for facilitating development like auto-completion

To install `steeleagle_sdk`, it is strongly recommended that you use [uv](https://docs.astral.sh/uv/). If you prefer another package manager,
`steeleagle_sdk` can be installed like any PyPI package. SteelEagle requires Python >= 3.11.

<Tabs>
  <TabItem value="uv" label="uv" default>
    ```bash
    uv add steeleagle_sdk
    ```
  </TabItem>
  <TabItem value="pip" label="pip">
    ```bash
    pip install steeleagle_sdk
    ```
  </TabItem>
  <TabItem value="conda" label="conda">
    ```bash
    conda install steeleagle_sdk
    ```
  </TabItem>
</Tabs>
