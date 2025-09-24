#!/usr/bin/env python3
"""
ACORD Document Processing CLI

Extracts a specific page from an ACORD document and processes it with Claude OCR.
"""

import click
import os
import sys
import json
import base64
from pathlib import Path
from io import BytesIO
from typing import Optional

# Add the project root to Python path so we can import from backend
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import boto3
    from botocore.exceptions import ClientError
    from pdf2image import convert_from_path
    from PIL import Image
    import PyPDF2
except ImportError as e:
    click.echo(f"Error: Missing required dependency: {e}", err=True)
    click.echo("Please run: pip install -r requirements.txt", err=True)
    sys.exit(1)


class ACORDProcessor:
    """Handles ACORD document processing with Claude OCR"""

    def __init__(self):
        self.model_id = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
        self.ocr_prompt = "Extract all text from this document. Preserve the original formatting and structure as much as possible, including line breaks, paragraphs, and spacing."
        self.bedrock_client = None

        # ACORD extraction prompts
        self.acord_125_prompt = """You are a data extraction specialist. Extract ALL information from the provided ACORD 125 insurance form document and return it in valid JSON format only. Do not include any explanatory text, comments, or markdown formatting - return only the JSON object.

Instructions:
1. Extract every field visible in the document, even if empty
2. Use null for empty/blank fields
3. Use boolean true/false for checkboxes (☒ = true, ☐ = false)
4. Preserve exact text formatting and spacing where relevant
5. Return only valid JSON - no additional text or formatting

JSON Structure:
{
  "agency_customer_id": "",
  "contact_information": {
    "accounting_records": {
      "contact_name": "",
      "primary_phone": {
        "number": "",
        "type": {
          "home": false,
          "business": false,
          "cell": false
        }
      },
      "secondary_phone": {
        "number": "",
        "type": {
          "home": false,
          "business": false,
          "cell": false
        }
      },
      "primary_email": "",
      "secondary_email": ""
    },
    "inspection": {
      "contact_name": "",
      "primary_phone": {
        "number": "",
        "type": {
          "home": false,
          "business": false,
          "cell": false
        }
      },
      "secondary_phone": {
        "number": "",
        "type": {
          "home": false,
          "business": false,
          "cell": false
        }
      },
      "primary_email": "",
      "secondary_email": ""
    }
  },
  "premises_information": [
    {
      "location_number": "",
      "building_number": "",
      "street": "",
      "city": "",
      "state": "",
      "county": "",
      "zip": "",
      "city_limits": {
        "inside": false,
        "outside": false
      },
      "interest": {
        "owner": false,
        "tenant": false
      },
      "full_time_employees": "",
      "part_time_employees": "",
      "annual_revenues": "",
      "occupied_area_sq_ft": "",
      "open_to_public_area_sq_ft": "",
      "total_building_area_sq_ft": "",
      "any_area_leased_to_others": "",
      "description_of_operations": ""
    }
  ],
  "nature_of_business": {
    "apartments": false,
    "condominiums": false,
    "contractor": false,
    "institutional": false,
    "manufacturing": false,
    "office": false,
    "restaurant": false,
    "retail": false,
    "service": false,
    "wholesale": false
  },
  "description_of_primary_operations": "",
  "date_business_started": "",
  "retail_stores_or_service_operations": {
    "installation_service_repair_work_percentage": "",
    "off_premises_installation_service_repair_work_percentage": ""
  },
  "description_of_operations_other_named_insureds": "",
  "additional_interest": {
    "interest_types": {
      "additional": false,
      "insured": false,
      "breach_of_warranty": false,
      "co_owner": false,
      "employee": false,
      "as_lessor": false,
      "leaseback": false,
      "lenders_loss_payable": false,
      "lienholder": false,
      "loss_payee": false,
      "mortgagee": false,
      "owner": false,
      "registrant": false,
      "trustee": false
    },
    "name_and_address": "",
    "rank": "",
    "reference_loan_number": "",
    "evidence": "",
    "certificate": false,
    "policy": false,
    "send_bill": false,
    "interest_in_item_number": "",
    "interest_end_date": "",
    "lien_amount": "",
    "phone": "",
    "fax": "",
    "email_address": "",
    "reason_for_interest": "",
    "location": "",
    "building": "",
    "vehicle": "",
    "boat": "",
    "airport": "",
    "aircraft": "",
    "item": "",
    "class": "",
    "item_description": ""
  }
}

Extract all data from the document and populate this JSON structure with the actual values found in the form. Return only the completed JSON object."""

        self.acord_140_prompt = """You are a data extraction specialist. Extract ALL information from the provided ACORD 140 Property Section insurance form document and return it in valid JSON format only. Do not include any explanatory text, comments, or markdown formatting - return only the JSON object.

Instructions:
1. Extract every field visible in the document, even if empty
2. Use null for empty/blank fields
3. Use boolean true/false for checkboxes (☒ = true, ☐ = false, X = true)
4. Preserve exact text formatting and spacing where relevant
5. Return only valid JSON - no additional text or formatting

JSON Structure:
{
  "agency_customer_id": "",
  "date": "",
  "agency_name": "",
  "carrier": "",
  "naic_code": "",
  "policy_number": "",
  "effective_date": "",
  "named_insured": "",
  "blanket_summary": [
    {
      "blanket_number": "",
      "amount": "",
      "type": ""
    }
  ],
  "premises_information": {
    "premises_number": "",
    "street_address": "",
    "building_number": "",
    "building_description": "",
    "occupancy": ""
  },
  "subject_of_insurance": [
    {
      "subject": "",
      "amount": "",
      "coins_percentage": "",
      "valuation": "",
      "causes_of_loss": "",
      "inflation_guard_percentage": "",
      "deductible": "",
      "deductible_type": "",
      "blanket_number": "",
      "forms_and_conditions_to_apply": ""
    }
  ],
  "additional_information": {
    "business_income_extra_expense": "",
    "value_reporting_information": ""
  },
  "additional_coverages": {
    "spoilage_coverage": {
      "enabled": false,
      "description_of_property_covered": "",
      "limit": "",
      "deductible": "",
      "refrigeration_maintenance_agreement": false
    },
    "options": {
      "breakdown_or_contamination": false,
      "power_outage": false,
      "selling_price": false
    },
    "sinkhole_coverage": {
      "required_in_florida": true,
      "accept_coverage": false,
      "reject_coverage": false,
      "limit": ""
    },
    "mine_subsidence_coverage": {
      "required_states": ["IL", "IN", "KY", "WV"],
      "accept_coverage": false,
      "reject_coverage": false,
      "limit": "",
      "deductible": "",
      "type": ""
    }
  },
  "construction_details": {
    "construction_type": "",
    "distance_to_hydrant": {
      "feet": "",
      "miles": ""
    },
    "fire_district": "",
    "code_number": "",
    "protection_class": "",
    "number_of_stories": "",
    "number_of_basements": "",
    "year_built": "",
    "total_area": "",
    "building_code": "",
    "tax_code": "",
    "roof_type": "",
    "other_occupancies": "",
    "grade": "",
    "wind_class": {
      "semi_resistive": false,
      "resistive": false
    },
    "property_designated_historical_landmark": ""
  },
  "building_improvements": {
    "wiring_year": "",
    "roofing_year": "",
    "plumbing_year": "",
    "heating_year": "",
    "other_year": ""
  },
  "heating_source": {
    "including_woodburning": false,
    "stove_or_fireplace_insert": false,
    "manufacturer": "",
    "date_installed": "",
    "primary_heat": {
      "boiler": false,
      "solid_fuel": false,
      "insurance_placed_elsewhere": ""
    },
    "secondary_heat": {
      "boiler": false,
      "solid_fuel": false,
      "insurance_placed_elsewhere": ""
    }
  },
  "fire_protection": {
    "premises_fire_protection": {
      "sprinklers_standpipes_co2_chemical": true,
      "sprinkler_percentage": "",
      "central_station": false,
      "local_gong": false
    },
    "fire_alarm": {
      "manufacturer": "",
      "central_station": false,
      "local_gong": false
    }
  },
  "burglar_alarm": {
    "type": "",
    "certificate_number": "",
    "expiration_date": "",
    "installed_and_serviced_by": "",
    "extent": "",
    "grade": "",
    "central_with_keys": false,
    "number_of_guards_watchmen": "",
    "clock_hourly": false
  },
  "exposures": {
    "right_exposure_distance": "",
    "left_exposure_distance": "",
    "front_exposure_distance": "",
    "rear_exposure_distance": "",
    "number_of_open_sides_on_structure": ""
  },
  "additional_interest": {
    "acord_45_attached": false,
    "interest_types": {
      "loss_payee": false,
      "mortgagee": false
    },
    "name_and_address": "",
    "rank": "",
    "evidence": "",
    "certificate": false,
    "reference_loan_number": "",
    "interest_in_item_number": "",
    "location": "",
    "building": "",
    "item": "",
    "class": "",
    "item_description": ""
  }
}

Extract all data from the document and populate this JSON structure with the actual values found in the form. Return only the completed JSON object."""

    def setup_bedrock_client(self):
        """Initialize AWS Bedrock client"""
        try:
            # Get credentials from environment
            access_key = os.environ.get('AWS_ACCESS_KEY_ID')
            secret_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
            region = os.environ.get('AWS_DEFAULT_REGION', 'us-east-1')

            if not access_key or not secret_key:
                raise ValueError("AWS credentials not found in environment variables")

            self.bedrock_client = boto3.client(
                'bedrock-runtime',
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=region
            )
            click.echo("✓ Successfully connected to AWS Bedrock")

        except Exception as e:
            raise click.ClickException(f"Failed to connect to AWS Bedrock: {str(e)}")

    def extract_page(self, input_pdf: str, page_number: int, output_dir: str) -> str:
        """Extract specific page from PDF and save as separate file"""
        if not os.path.exists(input_pdf):
            raise click.ClickException(f"Input file not found: {input_pdf}")

        # Create output directory
        os.makedirs(output_dir, exist_ok=True)

        # Generate output filename
        input_name = Path(input_pdf).stem
        output_filename = f"{input_name}_page_{page_number:04d}.pdf"
        output_path = os.path.join(output_dir, output_filename)

        try:
            with open(input_pdf, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                total_pages = len(pdf_reader.pages)

                if page_number < 1 or page_number > total_pages:
                    raise click.ClickException(f"Page {page_number} not found. Document has {total_pages} pages.")

                # Create new PDF with just the specified page
                pdf_writer = PyPDF2.PdfWriter()
                pdf_writer.add_page(pdf_reader.pages[page_number - 1])  # Convert to 0-based index

                # Save extracted page
                with open(output_path, 'wb') as output_file:
                    pdf_writer.write(output_file)

                click.echo(f"✓ Extracted page {page_number} to: {output_filename}")
                return output_path

        except Exception as e:
            raise click.ClickException(f"Error extracting page: {str(e)}")

    def ocr_with_claude(self, pdf_path: str, output_dir: str) -> dict:
        """OCR the extracted page using Claude"""
        if not self.bedrock_client:
            self.setup_bedrock_client()

        try:
            click.echo("Converting PDF to image...")
            # Convert PDF to image
            images = convert_from_path(pdf_path, dpi=300)

            if len(images) != 1:
                click.echo(f"Warning: Expected 1 page, got {len(images)} pages")

            # Process the image with Claude
            image = images[0]
            click.echo("Sending to Claude for OCR...")

            # Convert image to base64
            buffer = BytesIO()
            image.save(buffer, format='PNG')
            image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

            # Prepare Claude request
            body = json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 4000,
                "temperature": 0.1,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": image_base64
                                }
                            },
                            {
                                "type": "text",
                                "text": self.ocr_prompt
                            }
                        ]
                    }
                ]
            })

            # Call Claude via Bedrock
            response = self.bedrock_client.invoke_model(
                body=body,
                modelId=self.model_id,
                accept='application/json',
                contentType='application/json'
            )

            # Parse response
            response_body = json.loads(response.get('body').read())
            if 'content' in response_body and response_body['content']:
                ocr_text = response_body['content'][0].get('text', '')
            else:
                ocr_text = "Error: No text extracted by Claude"

            # Save OCR results
            pdf_name = Path(pdf_path).stem
            ocr_filename = f"{pdf_name}-claude-ocr.txt"
            ocr_path = os.path.join(output_dir, ocr_filename)

            with open(ocr_path, 'w', encoding='utf-8') as f:
                f.write(ocr_text)

            click.echo(f"✓ OCR completed: {ocr_filename} ({len(ocr_text)} characters)")

            return {
                "status": "success",
                "ocr_file": ocr_filename,
                "text_length": len(ocr_text),
                "pdf_file": Path(pdf_path).name
            }

        except ClientError as e:
            raise click.ClickException(f"AWS Bedrock error: {str(e)}")
        except Exception as e:
            raise click.ClickException(f"OCR processing error: {str(e)}")

    def determine_acord_type(self, ocr_text: str) -> str:
        """Determine if the document is ACORD 125 or ACORD 140 based on OCR text"""
        ocr_text_upper = ocr_text.upper()

        if "ACORD 125" in ocr_text_upper or "125" in ocr_text_upper:
            return "125"
        elif "ACORD 140" in ocr_text_upper or "140" in ocr_text_upper:
            return "140"
        else:
            # Default to 125 if cannot determine
            click.echo("Warning: Could not determine ACORD type, defaulting to ACORD 125")
            return "125"

    def extract_acord_data(self, ocr_text: str, output_dir: str, base_filename: str) -> dict:
        """Extract structured data from ACORD form using appropriate prompt"""
        if not self.bedrock_client:
            self.setup_bedrock_client()

        try:
            # Determine ACORD type
            acord_type = self.determine_acord_type(ocr_text)
            click.echo(f"Detected ACORD {acord_type} form")

            # Choose appropriate prompt
            if acord_type == "140":
                extraction_prompt = self.acord_140_prompt
                prompt_text = f"ACORD 140 Document Text:\n\n{ocr_text}\n\n{extraction_prompt}"
            else:
                extraction_prompt = self.acord_125_prompt
                prompt_text = f"ACORD 125 Document Text:\n\n{ocr_text}\n\n{extraction_prompt}"

            click.echo("Sending to Claude for data extraction...")

            # Prepare Claude request for data extraction
            body = json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 4000,
                "temperature": 0.1,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt_text
                    }
                ]
            })

            # Call Claude via Bedrock
            response = self.bedrock_client.invoke_model(
                body=body,
                modelId=self.model_id,
                accept='application/json',
                contentType='application/json'
            )

            # Parse response
            response_body = json.loads(response.get('body').read())
            if 'content' in response_body and response_body['content']:
                extraction_response = response_body['content'][0].get('text', '')
            else:
                extraction_response = "Error: No extraction data returned by Claude"

            # Try to parse as JSON
            try:
                # Clean response (remove potential markdown formatting)
                cleaned_response = extraction_response.strip()
                if cleaned_response.startswith('```json'):
                    cleaned_response = cleaned_response.replace('```json', '').replace('```', '').strip()
                elif cleaned_response.startswith('```'):
                    cleaned_response = cleaned_response.replace('```', '').strip()

                extracted_data = json.loads(cleaned_response)

                # Save extracted data to JSON file
                json_filename = f"{base_filename}-acord-{acord_type}-data.json"
                json_path = os.path.join(output_dir, json_filename)

                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(extracted_data, f, indent=2, ensure_ascii=False)

                click.echo(f"✓ Data extraction completed: {json_filename}")

                return {
                    "status": "success",
                    "acord_type": acord_type,
                    "extraction_file": json_filename,
                    "data": extracted_data
                }

            except json.JSONDecodeError as e:
                # Save raw response if JSON parsing fails
                raw_filename = f"{base_filename}-acord-{acord_type}-raw-response.txt"
                raw_path = os.path.join(output_dir, raw_filename)

                with open(raw_path, 'w', encoding='utf-8') as f:
                    f.write(f"JSON Parsing Error: {str(e)}\n\nRaw Response:\n{extraction_response}")

                click.echo(f"⚠️ JSON parsing failed, saved raw response: {raw_filename}")

                return {
                    "status": "partial_success",
                    "acord_type": acord_type,
                    "raw_response_file": raw_filename,
                    "error": f"JSON parsing failed: {str(e)}"
                }

        except ClientError as e:
            raise click.ClickException(f"AWS Bedrock error during extraction: {str(e)}")
        except Exception as e:
            raise click.ClickException(f"Data extraction error: {str(e)}")


@click.command()
@click.option('-i', '--input', 'input_file', required=True,
              help='Input ACORD PDF file path')
@click.option('-p', '--page', 'page_number', required=True, type=int,
              help='Page number to extract (1-based)')
@click.option('-o', '--output', 'output_dir', default='./acords',
              help='Output directory (default: ./acords)')
@click.option('--verbose', '-v', is_flag=True,
              help='Verbose output')
def process_acord(input_file: str, page_number: int, output_dir: str, verbose: bool):
    """
    Extract a specific page from an ACORD document and process it with Claude OCR.

    Example:
        python bin/acord.py -i documents/acord_form.pdf -p 2
        python bin/acord.py -i form.pdf -p 1 -o ./my_results
    """
    if verbose:
        click.echo(f"Input file: {input_file}")
        click.echo(f"Page number: {page_number}")
        click.echo(f"Output directory: {output_dir}")

    processor = ACORDProcessor()

    try:
        # Step 1: Extract the specific page
        click.echo(f"🔸 Extracting page {page_number} from {input_file}...")
        extracted_pdf = processor.extract_page(input_file, page_number, output_dir)

        # Step 2: OCR with Claude
        click.echo(f"🔸 Processing with Claude OCR...")
        ocr_result = processor.ocr_with_claude(extracted_pdf, output_dir)

        # Step 3: Extract structured data from OCR text
        click.echo(f"🔸 Extracting ACORD data...")
        ocr_file_path = os.path.join(output_dir, ocr_result['ocr_file'])

        # Read the OCR text
        with open(ocr_file_path, 'r', encoding='utf-8') as f:
            ocr_text = f.read()

        # Extract structured data
        base_filename = Path(extracted_pdf).stem
        extraction_result = processor.extract_acord_data(ocr_text, output_dir, base_filename)

        # Step 4: Display results
        click.echo("🎉 Processing completed successfully!")
        click.echo(f"   📄 Extracted PDF: {Path(extracted_pdf).name}")
        click.echo(f"   📝 OCR text file: {ocr_result['ocr_file']}")
        click.echo(f"   📊 OCR text length: {ocr_result['text_length']} characters")

        if extraction_result['status'] == 'success':
            click.echo(f"   🎯 ACORD {extraction_result['acord_type']} data: {extraction_result['extraction_file']}")
        elif extraction_result['status'] == 'partial_success':
            click.echo(f"   ⚠️ ACORD {extraction_result['acord_type']} raw response: {extraction_result['raw_response_file']}")
            click.echo(f"       Error: {extraction_result['error']}")

        click.echo(f"   📁 Output directory: {output_dir}")

    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Unexpected error: {str(e)}")


if __name__ == '__main__':
    process_acord()