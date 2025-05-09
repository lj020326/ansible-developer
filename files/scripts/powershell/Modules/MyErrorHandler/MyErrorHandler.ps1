﻿

## 
## following two functions for custom errors handling per
## http://www.powershellmagazine.com/2011/09/14/custom-errors/
##
## to throw a terminating exception:
##
#$errorRecord = New-ErrorRecord System.InvalidOperationException FileIsEmpty `
#    InvalidOperation $Path -Message "File '$Path' is empty."
#$PSCmdlet.ThrowTerminatingError($errorRecord)
##
## to throw a non-terminating exception:
##
#$errorRecord = New-ErrorRecord System.InvalidOperationException FileIsEmpty `
#    InvalidOperation $Path -Message "File '$Path' is empty."
#Write-Error -ErrorRecord $errorRecord
##

$logFile = $null
$logPath = $null
$logger = $null

function New-ErrorRecord {
    param(
        [Parameter(Mandatory = $true, Position = 0)]
        [System.String]
        $Exception,
        [Parameter(Mandatory = $true, Position = 1)]
        [Alias('ID')]
        [System.String]
        $ErrorId,
        [Parameter(Mandatory = $true, Position = 2)]
        [Alias('Category')]
        [System.Management.Automation.ErrorCategory]
        [ValidateSet('NotSpecified', 'OpenError', 'CloseError', 'DeviceError',
            'DeadlockDetected', 'InvalidArgument', 'InvalidData', 'InvalidOperation',
                'InvalidResult', 'InvalidType', 'MetadataError', 'NotImplemented',
                    'NotInstalled', 'ObjectNotFound', 'OperationStopped', 'OperationTimeout',
                        'SyntaxError', 'ParserError', 'PermissionDenied', 'ResourceBusy',
                            'ResourceExists', 'ResourceUnavailable', 'ReadError', 'WriteError',
                                'FromStdErr', 'SecurityError')]
        $ErrorCategory,
        [Parameter(Mandatory = $true, Position = 3)]
        [System.Object]
        $TargetObject,
        [Parameter()]
        [System.String]
        $Message,
        [Parameter()]
        [System.Exception]
        $InnerException
    )
    begin {
        # check for required function, if not defined...
        if (-not (Test-Path function:Get-AvailableExceptionsList)) {
            $message1 = "The required function Get-AvailableExceptionsList is not defined. " +
            "Please define it in the same scope as this function's and try again."
            $exception1 = New-Object System.OperationCanceledException $message1
            $errorID1 = 'RequiredFunctionNotDefined'
            $errorCategory1 = 'OperationStopped'
            $targetObject1 = 'Get-AvailableExceptionsList'
            $errorRecord1 = New-Object Management.Automation.ErrorRecord $exception1, $errorID1,
            $errorCategory1, $targetObject1
            # ...report a terminating error to the user
            $PSCmdlet.ThrowTerminatingError($errorRecord1)
        }
        # required function is defined, get "available" exceptions
        $exceptions = Get-AvailableExceptionsList
        $exceptionsList = $exceptions -join "`r`n"
    }
    process {
        # trap for any of the "exceptional" Exception objects that made through the filter
        trap [Microsoft.PowerShell.Commands.NewObjectCommand] {
            $PSCmdlet.ThrowTerminatingError($_)
        }
        # verify input exception is "available". if so...
        if ($exceptions -match "^(System\.)?$Exception$") {
            # ...build and save the new Exception depending on present arguments, if it...
            $_exception = if ($Message -and $InnerException) {
                # ...includes a custom message and an inner exception
                New-Object $Exception $Message, $InnerException
            } elseif ($Message) {
                # ...includes a custom message only
                New-Object $Exception $Message
            } else {
                # ...is just the exception full name
                New-Object $Exception
            }
            # now build and output the new ErrorRecord
            New-Object Management.Automation.ErrorRecord $_exception, $ErrorID,
            $ErrorCategory, $TargetObject
        } else {
            # Exception argument is not "available";
            # warn the user, provide a list of "available" exceptions and...
            Write-Warning "Available exceptions are:`r`n$exceptionsList" 
            $message2 = "Exception '$Exception' is not available."
            $exception2 = New-Object System.InvalidOperationExceptionn $message2
            $errorID2 = 'BadException'
            $errorCategory2 = 'InvalidOperation'
            $targetObject2 = 'Get-AvailableExceptionsList'
            $errorRecord2 = New-Object Management.Automation.ErrorRecord $exception2, $errorID2,
            $errorCategory2, $targetObject2
            # ...report a terminating error to the user
            $PSCmdlet.ThrowTerminatingError($errorRecord2)
        }
    }

 <#
 	.Synopsis
		Creates an custom ErrorRecord that can be used to report a terminating or non-terminating error.
 	.Description      
		Creates an custom ErrorRecord that can be used to report a terminating or non-terminating error.  
	.Parameter 
		Exception      The Exception that will be associated with the ErrorRecord.  
	.Parameter 
		ErrorID      A scripter-defined identifier of the error.  This identifier must be a non-localized string for a specific error type.  
	.Parameter 
		ErrorCategory      An ErrorCategory enumeration that defines the category of the error.  
	.Parameter 
		TargetObject      The object that was being processed when the error took place.  
	.Parameter 
		Message      Describes the Exception to the user.  
	.Parameter 
		InnerException      The Exception instance that caused the Exception association with the ErrorRecord.  
	.Example
	
		# advanced functions for testing 
		function Test-1 {  
			[CmdletBinding()]  
			param(  [Parameter(Mandatory = $true, ValueFromPipeline = $true)]  [String]  $Path  )  
			process {   
				foreach ($_path in $Path) {    
					$content = Get-Content -LiteralPath $_path -ErrorAction SilentlyContinue    
					if (-not $content) {
						$errorRecord = New-ErrorRecord InvalidOperationException FileIsEmpty InvalidOperation $_path -Message "File '$_path' is empty."
						$PSCmdlet.ThrowTerminatingError($errorRecord)
					}   
				}  
			} 
		} 
		
		function Test-2 {  
			[CmdletBinding()]  
			param(  [Parameter(Mandatory = $true, ValueFromPipeline = $true)]  [String]  $Path  )  
			process {   
				foreach ($_path in $Path) {
					$content = Get-Content -LiteralPath $_path -ErrorAction SilentlyContinue    
					if (-not $content) {
						$errorRecord = New-ErrorRecord InvalidOperationException FileIsEmptyAgain InvalidOperation $_path -Message "File '$_path' is empty again." -InnerException $Error[0].Exception     
						$PSCmdlet.ThrowTerminatingError($errorRecord)
					}   
				}  
			} 
		}
		
		# code to test the custom terminating error reports 
		Clear-Host 
		$null = New-Item -Path .\MyEmptyFile.bak -ItemType File -Force -Verbose 
		Get-ChildItem *.bak | Where-Object {-not $_.PSIsContainer} | Test-1 
		write-verbose System.Management.Automation.ErrorRecord  
		$Error[0] | Format-List * -Force 
		write-verbose Exception  
		$Error[0].Exception | Format-List * -Force Get-ChildItem *.bak | Where-Object {-not $_.PSIsContainer} | Test-2 
		write-verbose System.Management.Automation.ErrorRecord  
		$Error[0] | Format-List * -Force write-verbose Exception  
		$Error[0].Exception | Format-List * -Force Remove-Item .\MyEmptyFile.bak -Verbose      

	Description      
	===========      
	Both advanced functions throw a custom terminating error when an empty file is being processed.          
	-Function Test-2's custom ErrorRecord includes an inner exception, which is the ErrorRecord reported by function Test-1.      
	The test code demonstrates this by creating an empty file in the curent directory -which is deleted at the end- and passing its path to both test functions.      
	The custom ErrorRecord is reported and execution stops for function Test-1, then the ErrorRecord and its Exception are displayed for quick analysis.      
	Same process with function Test-2; after analyzing the information, compare both ErrorRecord objects and their corresponding Exception objects.          
	-In the ErrorRecord note the different Exception, CategoryInfo and FullyQualifiedErrorId data.          
	-In the Exception note the different Message and InnerException data.  
	
	.Example      
		$errorRecord = New-ErrorRecord System.InvalidOperationException FileIsEmpty InvalidOperation $Path -Message "File '$Path' is empty." 
		$PSCmdlet.ThrowTerminatingError($errorRecord)
		
	Description      
	===========      
	A custom terminating ErrorRecord is stored in variable 'errorRecord' and then it is reported through $PSCmdlet's ThrowTerminatingError method.      
	The $PSCmdlet object is only available within advanced functions.  
	.Example      
		$errorRecord = New-ErrorRecord System.InvalidOperationException FileIsEmpty InvalidOperation $Path -Message "File '$Path' is empty." 
		Write-Error -ErrorRecord $errorRecord
		
	Description      
	===========      
	A custom non-terminating ErrorRecord is stored in variable 'errorRecord' and then it is reported through the Write-Error Cmdlet's ErrorRecord parameter.  
	.Inputs      
		System.String  
	.Outputs      
		System.Management.Automation.ErrorRecord  
	.Link      
		Write-Error      
		Get-AvailableExceptionsList  
	.Notes      
		Name:      New-ErrorRecord      
		Author:    Robert Robelo      
		LastEdit:  08/24/2011 12:35  
#>
}

function Get-AvailableExceptionsList {
    [CmdletBinding()]
    param()
    end {
        $irregulars = 'Dispose|OperationAborted|Unhandled|ThreadAbort|ThreadStart|TypeInitialization'
        [AppDomain]::CurrentDomain.GetAssemblies() | ForEach-Object {
            $_.GetExportedTypes() -match 'Exception' -notmatch $irregulars |
            Where-Object {
                $_.GetConstructors() -and $(
                $_exception = New-Object $_.FullName
                New-Object Management.Automation.ErrorRecord $_exception, ErrorID, OpenError, Target
                )
            } | Select-Object -ExpandProperty FullName
        } 2> $null
    }

 <#  
 	.Synopsis      
		Retrieves all available Exceptions to construct ErrorRecord objects.  
	.Description      
		Retrieves all available Exceptions in the current session to construct ErrorRecord objects.  
	.Example
		$availableExceptions = Get-AvailableExceptionsList      

	Description      
	===========      
		Stores all available Exception objects in the variable 'availableExceptions'.  

	.Example      
		Get-AvailableExceptionsList | Set-Content $env:TEMP\AvailableExceptionsList.txt      

	Description      
	===========      
		Writes all available Exception objects to the 'AvailableExceptionsList.txt' file in the user's Temp directory.  
	.Inputs     
		None  
	.Outputs     
		System.String  
	.Link      
		New-ErrorRecord  
	.Notes      
		Name:      Get-AvailableExceptionsList      
		Author:    Robert Robelo      
		LastEdit:  08/24/2011 12:35
#>
}
